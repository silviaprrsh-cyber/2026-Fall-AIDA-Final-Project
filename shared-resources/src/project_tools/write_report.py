from project_paths import resolve_runtime_path, archive_relative
import csv
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from rdr.storage import DATA, ROOT

def read(name):return json.loads((resolve_runtime_path(DATA/name)).read_text(encoding='utf-8'))

def export(name,rows,fields):
    with (resolve_runtime_path(DATA/'processed'/name)).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)

def write_language_reports(lines):
    """Keep English and local Chinese reports separate without changing raw evidence."""
    combined='\n'.join(lines)
    zh,en=combined.split('# English translation',1)
    zh=zh.rstrip().removesuffix('---').rstrip()
    en=en.strip()
    etl=read('reports/etl_validation.json')
    latest=read('reports/station_timestamp_export/results.json')
    water_counts=Counter(r['query_data_status'] for r in latest['rows'] if r['station_type']=='hydrometric')
    run=latest['run']
    date=f'{run[:4]}-{run[4:6]}-{run[6:8]}'
    notes_zh=[
        '## 当前项目状态与后续核对','',
        '- 目标为覆盖约 724 km 主干及整个流域的准实时水情和潜在漫岸风险监测系统；本报告根据已有归档更新，不代表重新联网验证。',
        '- 用户已收到政府回信、数据使用许可及下载链接。四份政府测量 ZIP 和解压资料位于 `data/sources/alberta_flood_surveys/manual/`；具体使用条件以政府许可为准。',
        f'- 已归档 ETL（{etl["generated_at"]}）包含 {etl["sections"]:,} 条断面线、{etl["survey_points"]:,} 个点、{etl["profiles"]:,} 个候选剖面；实际断面风险仍为无法判定，不能把数据已取得写成水力条件全部已验证。',
        f'- 较新的源端时间戳查询快照为 {date}：{water_counts["realtime_record_returned"]} 个水文站有 48 小时内记录，{water_counts["realtime_record_older_than_48h"]} 个记录较旧，{water_counts["historical_daily_only"]} 个仅返回历史日值，{water_counts["no_realtime_record_returned"]} 个未返回观测。这是查询时的状态，不是当前在线率。',
        '- 实际站端传输时间未由所选公开接口明确提供；观测、提供方处理、本地接收时间必须分开。汇总文件为 `data/processed/station_timestamps/Red_Deer_River_Station_Source_Timestamps.csv`。',
        '- 当前四个主干输入站为 05CA009、05CC002、05CE001、05CK004。其他主干站返回有效数据时，应核实坐标和河网关系，按上下游顺序接入；不要把串联站点流量直接累加。',
        '- 采集代码位于 `API/`，来源数据分别位于 `data/sources/<source>/`。8 个已完成的一次性迁移和旧文档处理脚本已移除；一次性 API 脚本保留。',
        '- 现有 HTTP 采集与本地 ETL 分开运行，尚未形成自动更新的完整预报流程。Datamart 持续获取前须处理 AMQPS 通知要求；本次未启动采集。',
        '- 详细方法见 [ETL 说明](../../ETL_REFERENCECN.md)，手动资料见 [测量资料检查](manual_data_reviewCN.md)。','']
    notes_en=[
        '## Current project status and follow-up checks','',
        '- The final goal is near-real-time water monitoring and potential overbank-risk estimation across the approximately 724 km mainstem and basin. This report updates existing archive evidence; it is not a new online validation.',
        '- The user has received the government reply, data-use permission and download links. Four government survey ZIPs and extracted files are in `data/sources/alberta_flood_surveys/manual/`; use remains subject to the government terms.',
        f'- Archived ETL ({etl["generated_at"]}) contains {etl["sections"]:,} section lines, {etl["survey_points"]:,} points and {etl["profiles"]:,} candidate profiles. Actual section risks remain indeterminate; having data does not establish verified hydraulic conditions.',
        f'- The newer source-timestamp snapshot dated {date} contains {water_counts["realtime_record_returned"]} water stations with records within 48 hours, {water_counts["realtime_record_older_than_48h"]} with older records, {water_counts["historical_daily_only"]} with historical daily values only and {water_counts["no_realtime_record_returned"]} returning no observations. These are snapshot statuses, not current online availability.',
        '- Selected public interfaces do not explicitly expose actual station transmission time. Keep observation, provider processing and local receipt times separate. The summary is `data/processed/station_timestamps/Red_Deer_River_Station_Source_Timestamps.csv`.',
        '- The four selected mainstem inputs are 05CA009, 05CC002, 05CE001 and 05CK004. Incorporate additional valid mainstem stations in upstream-to-downstream order after checking coordinates and network relationships; do not directly sum serial gauge flows.',
        '- Acquisition code lives in `API/`, and each source has its own `data/sources/<source>/` directory. Eight completed migration and old document-editing utilities were removed; one-shot API scripts remain.',
        '- HTTP acquisition and local ETL run separately; the complete automatically updating forecast workflow is not implemented. Address the AMQPS notification requirement before ongoing Datamart retrieval. This update starts no acquisition.',
        '- See the [ETL reference](../../ETL_REFERENCE.md) and [manual survey review](manual_data_review.md).','']
    def insert(text, notes):
        title,body=text.split('\n',1)
        return title+'\n\n'+'\n'.join(notes)+'\n'+body.lstrip()+'\n'
    (resolve_runtime_path(DATA/'reports/coverage_reportCN.md')).write_text(insert(zh,notes_zh),encoding='utf-8')
    (resolve_runtime_path(DATA/'reports/coverage_report.md')).write_text(insert(en,notes_en),encoding='utf-8')


def main(*, docs_only=False):
    config=json.loads((resolve_runtime_path(ROOT/'config/stations.json')).read_text(encoding='utf-8'))
    stations=config['stations'];enabled=[s for s in stations if s['enabled']]
    hydro=read('reports/hydrometric_validation.json');hc=Counter(h.get('data_status','error') for h in hydro)
    outlets=read('processed/tributary_outlets.json');network=read('reports/confluence_summary.json')
    pdfs=read('reports/pdf_content_inventory.json');nhn=read('processed/nhn_inventory.json')
    partner_path=resolve_runtime_path(DATA/'reports/partner_precipitation_check.json')
    partner=json.loads(partner_path.read_text(encoding='utf-8')) if partner_path.exists() else None
    if not docs_only:
        export('station_master.csv',stations,['station_id','name','watercourse','kind','longitude','latitude','status','realtime_metadata','water_data_status','selected_monitoring_point','enabled','mode','interval_seconds','cadence_confidence'])
        export('weather_links.csv',[s['weather_link'] for s in stations],['station_id','weather_id','weather_name','distance_km','status','collocated','precipitation_field','precipitation_period_seconds'])
        export('tributary_outlets.csv',outlets,['watercourse','parent_river','longitude','latitude','direct_to_mainstem','selected_station_id','selection_method','at_mouth','geometry_gap_m','mouth_accuracy'])
    lines=['# 数据覆盖与归档验证报告','',f"以下目录及配置快照时间：{config['generated_at_utc']}（UTC）。对应的一次性验证与静态下载未启动持续采集；此时间不是本次文档更新时间，也不是最新观测时间。",'',
        '## 早期归档目录与验证结果','',
        f'- WSC 水系索引与 GeoMet 元数据合并：{len(stations)} 条站点记录，其中干流 12 条、坝/水库控制节点 2 条。索引中的历史站、停用站和无观测站均保留。',
        f"- 验证结果：{hc['realtime_available']} 条近期实时数据、{hc['historical_only']} 条仅历史数据、{hc['stale_realtime']} 条过期实时记录、{hc['no_observations']} 条未返回观测。这里“近期”为距验证时刻不超过 48 小时，不代表所有站当前一分钟都在线。",
        f'- 所有 {len(stations)} 个点都有通过数值降水字段检查的气象关联；实际关联到 10 个 ECCC 气象站。最近可用气象站距离最大 {max(s["weather_link"].get("distance_km",0) for s in stations):.3f} km，详见 weather_links.csv。气象并非原地测量，不插值、不伪造降水。',
        f'- 已建立 {network["named_mouths"]} 条具名水系汇合记录，其中 {network["direct_mainstem_named_mouths"]} 条直接连接干流，{network["with_same_river_gauge"]} 条匹配到同一河流的 WSC 站。',
        f'- 默认启用 {len(enabled)} 个去重监测点（干流、控制节点、匹配支流）。其中 {sum(s["mode"]=="water_and_weather" for s in enabled)} 个有近期水文及气象，{sum(s["mode"]=="weather_only" for s in enabled)} 个当前只能自动获取气象；不会把历史水文重复抓取后当成实时数据。',
        f'- 一次性下载 {len(nhn)} 个联邦 NHN 水系包，覆盖 05CA—05CK 及 Saskatchewan 末端 05CK002；保留原始 ZIP 和原有坐标定义。',
        '- Alberta 河网：流域内/相交常年河段 8,591 条、间歇河段/相关线 51,215 条、水体面 5,104 个。下载前查询 ID 全集并逐页验证，无静默截断。原始分页覆盖包围盒，processed 层再按流域边界筛选。',
        f'- 下载 {len(pdfs)} 份官方报告/修订，共 {sum(p["pages"] for p in pdfs)} 页。包括 Upper Red Deer、Red Deer、Markerville、Drumheller、Didsbury 和 Stettler。',
        '', '## 采集频率的证据与限制','',
        '- 水文持续采集选用 ECCC Datamart hourly CSV；官方明确其文件每小时更新。GeoMet JSON 已作一次验证，但 DATETIME 仅为观测时间，不能证明发布频率。',
        '- 气象持续采集使用 SWOB：通过单次响应中的 processed_date_tm 估计实际发布节奏，观察到约 60 秒或 3600 秒；气象记录时间和发布处理时间分别保存。',
        '- **SWOB 没有已核实的逐站固定发布 SLA。这些间隔是样本估计，不能称为官方已确认值。** 单次验证无法证明未来发布节奏；不为核实频率而偷偷持续轮询。',
        '- 各水文、气象源按自身 publication_interval_seconds 独立调度，共用来源去重。水文站计算窗口由其水文发布间隔和观测时间定义，不限制气象采集频率。旧 interval_seconds 仅兼容保留，不驱动调度。',
        '- 未知间隔不默认补值；自定义时需在 config/stations.json 写入间隔及依据。多个点共用气象源时，按源缓存，避免重复请求。',
        '- 在终端输入 stop 回车、Ctrl+C 或关闭标准输入，会停止新请求；已开始的 HTTP 请求完成或超时后退出。单请求连接/读取超时为 15/20 秒，原始响应先落盘。',
        '', '## 未完成覆盖与真实数据缺口','',
        '- **整个流域的完整数值河床、逐断面测量点和可运行 HEC-RAS 工程尚未取得。** 公开页面提供的 PDF 不等于原始测量/模型文件；河网平面线与面也不包含实测水下高程。',
        '- 早期公开 Drumheller 测量报告 PDF 第 170—171 页列出原始数据名称，但公开页面及 PDF 附件未提供对应文件。后来已通过政府提供的途径取得四套测量资料；数据名称和实际图层需以已保存包及检查报告为准。',
        '- 因此不能声称 724 km 河床或每个支流汇入口的横断面完整覆盖。现有报告覆盖若干研究河段，并非全河；没有用 DEM 或插值冒充河床测深。',
        '- 无测站的支流不能产生观测数据。无同河测站会留空，不借用另一条河或主河站充当该支流站。湖泊、水库和渠道站保留在完整站点目录中。',
        f'- {network["selection_requires_review"]} 条汇合记录因河网连接不完整，只能以同名河流测站到汇入口的直线距离暂选；selection_method 已标记 provisional。它们不是已确认的沿河最近结果。',
        '- NHN 旧河网存在未标注流向、同名水系、缺名河段和支汊，仍有未解析记录。详见 tributary_geometry_gaps.json 与 tributary_topology_gaps.json；550 条未命名干流入流候选另存，不等同于 550 条已核定支流。',
        '- 范围是公开 WSC/ECCC 站网与上述公开 GIS。没有证据证明已枚举所有地方、私人或临时监测设施。',
        '', '## 无近期水文的干流站','', '| Station | 名称 | 验证结果 |', '|---|---|---|']
    for s in stations:
        if s['kind']=='MAINSTEM' and s['water_data_status']!='realtime_available':lines.append(f"| {s['station_id']} | {s['name']} | {s['water_data_status']} |")
    lines+=['','## 来源与文件','',
        '- [WSC 完整站点索引](https://wateroffice.ec.gc.ca/station_metadata/reference_index_download_e.html)',
        '- [ECCC GeoMet 水文站](https://api.weather.gc.ca/collections/hydrometric-stations)',
        '- [ECCC SWOB 实时观测](https://api.weather.gc.ca/collections/swob-realtime)',
        '- [水文小时文件发布说明](https://eccc-msc.github.io/open-data/msc-data/obs_hydrometric/readme_hydrometric-datamart_en/)',
        '- [SWOB 数据说明](https://eccc-msc.github.io/open-data/msc-data/obs_station/readme_obs_insitu_swobdatamart_en/)',
        '- [Alberta 最终洪水研究目录](https://www.alberta.ca/final-flood-maps)',
        '- [National Hydro Network](https://open.canada.ca/data/en/dataset/a4b190fe-e090-4e6d-881e-b87956c07977)',
        '', '公开水文、气象和 GIS 获取响应旁的 .meta.json 记录 URL、UTC 获取时间、状态码、SHA-256 和字节数。这些公开接口使用匿名 HTTPS；卫星认证使用 .env 凭据，并以运行清单保存来源；手动测量 ZIP 通过资料清单保留校验信息。','']
    if partner:
        lines+=['## 省级气象来源补查与站点匹配复核','',
            f'- 对原最近站搜索遇到的 {len(partner["stations"])} 个 Alberta 农业站，各取一次最新公开 SWOB XML：含有效降水量的样本为 {partner["valid_precipitation_count"]} 个。因此没有用这些站替换已有降水来源。结果仅说明本次样本；不能推断这些站永远不测降水。',
            '- avg_wnd_spd_pcpn_gag_pst1hr 是雨量计高度处的风速（km/h），不是降水量。原始 XML、提供方署名及检查结果保存在 data 内。',
            '- Spring Creek 的 05CJ010 和 Sylvan Creek 的 05CC004 与所有已绘制的同名河道距离超过 500 m，未自动选作汇入口替代站。完整站点档案及首次验证仍保留；需要补足河道连接或位置证据。',
            '- 若某候选站的已知沿河距离小于其他所有未连通候选站的直线距离，可利用直线距离下界确认最近站；否则继续标为暂定。',
            '- 本次补查脚本：API/check_partner_precipitation.py；结果：data/reports/partner_precipitation_check.json。','']
    lines += [
        '---', '', '# English translation', '', '# Data coverage and archived validation report', '',
        f"Inventory/configuration snapshot below: {config['generated_at_utc']} UTC. The corresponding one-time validation and static downloads did not start continuous collection. This is neither the documentation update time nor the latest observation time.", '',
        '## Earlier archived inventory and validation results', '',
        f'- The WSC drainage index and GeoMet metadata were combined into {len(stations)} station records, including 12 mainstem stations and 2 dam or reservoir control points. Historical, inactive and observation-free stations remain in the catalogue.',
        f"- Validation found {hc['realtime_available']} stations with recent real-time records, {hc['historical_only']} with historical records only, {hc['stale_realtime']} with stale real-time records and {hc['no_observations']} returning no observations. Recent means within 48 hours of validation, not that every station is continuously online.",
        f'- All {len(stations)} points have weather links that passed numerical precipitation checks, using 10 distinct ECCC stations. The maximum distance to a verified available weather station is {max(s["weather_link"].get("distance_km",0) for s in stations):.3f} km; see weather_links.csv. These are not colocated observations. No precipitation was interpolated or fabricated.',
        f'- There are {network["named_mouths"]} named confluence records, including {network["direct_mainstem_named_mouths"]} direct mainstem connections and {network["with_same_river_gauge"]} matched same-river WSC gauges.',
        f'- The default configuration enables {len(enabled)} distinct monitoring points across the mainstem, controls and matched tributaries. Of these, {sum(s["mode"]=="water_and_weather" for s in enabled)} have recent hydrometric and weather data, and {sum(s["mode"]=="weather_only" for s in enabled)} currently collect weather only. Historical hydrometric records are not repeatedly retrieved and presented as real-time observations.',
        f'- {len(nhn)} federal NHN packages were downloaded once, covering 05CA through 05CK and the downstream Saskatchewan package 05CK002. Original ZIP files and coordinate definitions are retained.',
        '- Alberta network features within or intersecting the basin comprise 8,591 permanent stream segments, 51,215 intermittent stream segments or related lines, and 5,104 waterbody polygons. Complete object-ID sets were queried before downloading and checked page by page to avoid silent truncation. Raw pages cover bounding boxes; processed outputs are filtered by basin boundaries.',
        f'- {len(pdfs)} official reports or amendments were downloaded, totalling {sum(p["pages"] for p in pdfs)} pages. They cover Upper Red Deer, Red Deer, Markerville, Drumheller, Didsbury and Stettler.', '',
        '## Evidence and limits of collection frequency', '',
        '- Continuous hydrometric collection uses ECCC Datamart hourly CSV files, documented as updated hourly. GeoMet JSON was validated once, but DATETIME describes observation time and does not establish publication frequency.',
        '- Continuous weather collection uses SWOB. Differences in processed_date_tm within a single response estimate the publication pattern, approximately 60 or 3,600 seconds in the samples. Observation and publication-processing timestamps are retained separately.',
        '- **No official fixed station-specific SWOB publication SLA has been verified. These intervals are sample estimates, not officially confirmed values.** One-time validation cannot establish future publication behaviour; continuous polling was not started merely to determine frequency.',
        '- Each water and weather source has an independent publication_interval_seconds schedule; shared sources are deduplicated. Calculation windows follow each water station publication interval and observation times without slowing weather collection. Legacy interval_seconds is retained for compatibility, not scheduling.',
        '- Unknown intervals are not silently defaulted. Custom settings require an interval and evidence in config/stations.json. Shared weather sources are cached by source to avoid duplicate requests.',
        '- Entering stop and pressing Enter, pressing Ctrl+C, or closing standard input stops new requests. In-flight HTTP requests finish or time out before exit. Connection and read timeouts are 15 and 20 seconds respectively; original responses are saved first.', '',
        '## Incomplete coverage and actual data gaps', '',
        '- **Complete numerical riverbed data, surveyed points for every cross-section and runnable HEC-RAS projects for the whole basin have not been obtained.** Public PDFs are not original survey or model files; planimetric river lines and polygons do not supply measured underwater elevations.',
        '- Pages 170–171 of the earlier public Drumheller survey PDF name original datasets that were not provided by the public resource list or PDF attachments. Four survey packages were subsequently obtained through the government-provided access; use the saved packages and inspection reports for their actual filenames and layers.',
        '- Full riverbed coverage along 724 km, or cross-sections at every tributary mouth, therefore cannot be claimed. Existing reports cover selected study reaches, not the entire river. DEMs and interpolation have not been presented as bathymetric surveys.',
        '- Ungauged tributaries cannot produce measured observations. Where no same-river gauge exists, the association remains empty; another tributary or mainstem gauge is not substituted as that tributary’s gauge. Lake, reservoir and canal stations remain in the full catalogue.',
        f'- {network["selection_requires_review"]} confluence records use provisional straight-line selection because river-network connections are incomplete. selection_method marks these as provisional; they are not confirmed nearest-gauge results along the river.',
        '- The older NHN network contains unknown flow directions, repeated watercourse names, unnamed reaches and branches, with unresolved records. See tributary_geometry_gaps.json and tributary_topology_gaps.json. The 550 unnamed mainstem inflow candidates are retained separately and are not equivalent to 550 confirmed tributaries.',
        '- Scope is the public WSC/ECCC station network and the public GIS sources above. There is no evidence that all local, private or temporary monitoring facilities have been enumerated.', '',
        '## Mainstem stations without recent hydrometric observations', '',
        '| Station | Name | Validation result |', '|---|---|---|'
    ]
    for s in stations:
        if s['kind']=='MAINSTEM' and s['water_data_status']!='realtime_available':
            lines.append(f"| {s['station_id']} | {s['name']} | {s['water_data_status']} |")
    lines += ['', '## Sources and files', '',
        '- [Complete WSC station index](https://wateroffice.ec.gc.ca/station_metadata/reference_index_download_e.html)',
        '- [ECCC GeoMet hydrometric stations](https://api.weather.gc.ca/collections/hydrometric-stations)',
        '- [ECCC SWOB real-time observations](https://api.weather.gc.ca/collections/swob-realtime)',
        '- [Hydrometric hourly publication documentation](https://eccc-msc.github.io/open-data/msc-data/obs_hydrometric/readme_hydrometric-datamart_en/)',
        '- [SWOB documentation](https://eccc-msc.github.io/open-data/msc-data/obs_station/readme_obs_insitu_swobdatamart_en/)',
        '- [Alberta final flood studies](https://www.alberta.ca/final-flood-maps)',
        '- [National Hydro Network](https://open.canada.ca/data/en/dataset/a4b190fe-e090-4e6d-881e-b87956c07977)', '',
        'Public hydrometric, weather and GIS response sidecars record URL, UTC retrieval time, HTTP status, SHA-256 and byte count. These public interfaces use anonymous HTTPS. Satellite authentication uses .env credentials and run manifests; manual survey ZIP checksums are retained in archive inventories.', '']
    if partner:
        lines += ['## Additional provincial weather checks and station matching review', '',
            f'- One latest public SWOB XML was checked for each of the {len(partner["stations"])} Alberta agricultural stations encountered during the original nearest-station search. {partner["valid_precipitation_count"]} samples contained valid precipitation, so they did not replace the existing precipitation sources. This describes the samples only, not whether these stations ever measure precipitation.',
            '- avg_wnd_spd_pcpn_gag_pst1hr is wind speed at precipitation-gauge height in km/h, not precipitation. Original XML, provider attribution and check results are retained under data.',
            '- Spring Creek gauge 05CJ010 and Sylvan Creek gauge 05CC004 are more than 500 m from all mapped same-name river geometry and were not automatically selected as mouth substitutes. Their catalogue records and initial validation remain available; additional connectivity or location evidence is required.',
            '- If a candidate’s verified river distance is shorter than the straight-line distance of every candidate with an unresolved route, the straight-line lower bound establishes the nearest gauge. Otherwise the selection remains provisional.',
            '- Check script: API/check_partner_precipitation.py. Results: data/reports/partner_precipitation_check.json.', '']
    write_language_reports(lines)
    print('Wrote coverage_report.md and coverage_reportCN.md' + ('' if docs_only else ' and CSV indexes'))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Build English and Chinese coverage reports from local archives')
    parser.add_argument('--docs-only',action='store_true',help='Update Markdown without rewriting CSV indexes')
    main(docs_only=parser.parse_args().docs_only)
