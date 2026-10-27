"""Normalize the provider's station-index CSV without changing its original bytes."""
import csv
import hashlib
import io
from pathlib import Path

from rdr.storage import save_json


HEADER = [
    'Station Number', 'Water Course', 'Latitude', 'Longitude',
    'Gross Drainage Area (km2)', 'Effective Drainage Area (km2)',
    'Land Description', 'Year From', 'Year To', 'Data Type', 'Gauge Type',
    'Operation Schedule', 'Published', 'Station Class', 'River Type',
    'Regulated Since', 'Contributed By', 'Costing Agency',
]


def parse_provider_line(line):
    """Accept literal quotes within quoted names and unquoted DMS coordinates.

    This provider exports one physical line per record. A single quote inside a
    quoted field closes it only before a comma or end of line. Other single
    quotes are literal characters. Ambiguous/multiline input is not guessed.
    """
    fields = []
    value = []
    quoted = False
    repairs = 0
    index = 0
    while index < len(line):
        char = line[index]
        following = line[index + 1:index + 2]
        if quoted:
            if char == '"' and following == '"':
                value.append('"')
                index += 2
                continue
            if char == '"' and following in ('', ','):
                quoted = False
            else:
                value.append(char)
                repairs += char == '"'
        elif char == ',':
            fields.append(''.join(value))
            value = []
        elif char == '"' and not value:
            quoted = True
        else:
            value.append(char)
        index += 1
    if quoted:
        raise ValueError('Unclosed quoted field; multiline station records are unsupported')
    fields.append(''.join(value))
    return fields, repairs


def normalize_station_index(source, destination):
    """Write a strict 18-column derived CSV with input/output checksums and fixes."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('The normalized CSV must not overwrite the source')
    raw = source.read_bytes()
    lines = raw.decode('utf-8-sig').splitlines()
    if not lines or next(csv.reader([lines[0]], strict=True)) != HEADER:
        raise ValueError('Unexpected station-index header')
    rows = []
    corrections = []
    for line_number, line in enumerate(lines[1:], 2):
        fields, quotes = parse_provider_line(line)
        original_columns = len(fields)
        if len(fields) > len(HEADER):
            if any(value.strip() for value in fields[len(HEADER):]):
                raise ValueError(f'Nonempty extra fields on station-index line {line_number}')
            fields = fields[:len(HEADER)]
        if len(fields) < len(HEADER):
            # Only blank rows and one-field footer notes may omit columns.
            if len(fields) != 1 or fields[0].strip()[:2].isdigit():
                raise ValueError(f'Incomplete station-index row on line {line_number}')
            fields += [''] * (len(HEADER) - len(fields))
        if quotes or original_columns != len(HEADER):
            corrections.append({'source_line': line_number,
                                'literal_quotes_preserved': quotes,
                                'original_columns': original_columns,
                                'normalized_columns': len(HEADER)})
        rows.append(fields)
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\r\n')
    writer.writerow(HEADER)
    writer.writerows(rows)
    text = buffer.getvalue()
    if list(csv.reader(io.StringIO(text), strict=True)) != [HEADER, *rows]:
        raise ValueError('Normalized CSV failed the strict round-trip check')
    body = text.encode('utf-8-sig')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.tmp')
    temporary.write_bytes(body)
    temporary.replace(destination)
    save_json(destination.with_suffix(destination.suffix + '.meta.json'), {
        'normalization_version': 1,
        'source_path': source.as_posix(),
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'normalized_sha256': hashlib.sha256(body).hexdigest(),
        'rows': len(rows), 'columns': len(HEADER),
        'rule': 'Preserve literal name quotes, remove empty surplus columns, and pad blank/footer rows.',
        'corrections': corrections,
    })
    return destination
