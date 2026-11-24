// Red Deer River read-only research receiver for Windows.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Reflection;
using System.Runtime.Versioning;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: AssemblyTitle("Red Deer River Research Receiver")]
[assembly: AssemblyProduct("AIDA 2156 Red Deer River Course Demo")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: TargetFramework(".NETFramework,Version=v4.8", FrameworkDisplayName = ".NET Framework 4.8")]

namespace RedDeerResearch
{
    internal sealed class Reading
    {
        public string Id, Title, Status, Period, Source;
        public double? Value;
        public DateTimeOffset? Clock, Retrieved, WindowEnd;
    }

    internal sealed class Group
    {
        public int Hours;
        public Reading[] Depths;
        public DateTimeOffset? Target, Generated;
        public string State, Note;
    }

    internal sealed class Snapshot
    {
        public string Mode, State, Warning, BackendError;
        public DateTimeOffset Generated;
        public Reading[] Flows;
        public Reading Rain;
        public Group[] Groups;

        public DateTimeOffset? Newest
        {
            get
            {
                return Flows.Concat(new[] { Rain }).Where(r => r.Value.HasValue)
                    .Select(r => r.Clock).DefaultIfEmpty().Max();
            }
        }
    }

    internal static class Contract
    {
        public const string DefaultUrl = "http://127.0.0.1:8765";
        public const string Disclaimer = "COURSE DEMO ONLY. Not for real flood forecasting, warnings, emergency response, evacuation, river operations, or safety decisions.";
        public const string Limit = "Estimates are limited by upstream travel time and records already available at issuance. No later upstream flows are forecast; a horizon with missing or not-yet-available data is unavailable.";
        private const int MaxBytes = 128 * 1024;
        private static readonly Regex Zone = new Regex(@"(Z|[+-]\d\d:\d\d)$", RegexOptions.CultureInvariant);
        private static readonly Regex Bearer = new Regex(@"^[A-Za-z0-9._~+/\-]+=*\z", RegexOptions.CultureInvariant);
        private static readonly string[] Stations = { "05CB007", "05CB001", "05CC007", "05CC002" };
        private static readonly string[] StationNames = {
            "Dickson Dam Tunnel Outlet", "Little Red Deer River near the Mouth",
            "Medicine River near Eckville", "Red Deer River at Red Deer"
        };
        private static readonly Dictionary<string, string> Reasons = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            { "future_upstream_observations_required", "The required upstream observations fall after issuance." },
            { "dickson_exact_sample_unavailable_for_projection", "The required Dickson Dam reading was not available at issuance." },
            { "short_route_rain_window_incomplete_for_projection", "The required short-route precipitation window is incomplete." },
            { "little_exact_nominal_sample_absent", "The required Little Red Deer River reading was not available at issuance." },
            { "little_exact_sample_unavailable_at_issuance", "The required Little Red Deer River reading was not available at issuance." },
            { "waiting_for_first_poll", "The service is waiting for its first data collection." },
            { "medicine_candidate_source_span_incomplete", "The required Medicine River history is incomplete." },
            { "medicine_no_arriving_parcels", "No qualifying Medicine River observations could be routed to this target." },
            { "medicine_rain_window_incomplete_for_projection", "The required Medicine River precipitation window is incomplete." },
            { "database_unavailable", "The server could not read or commit its data store." },
            { "cached_snapshot_stale", "The server snapshot is too old for a current estimate." },
            { "model_error", "The server could not compute an estimate." }
        };

        public static string Url(string raw)
        {
            string value = (raw ?? "").Trim();
            Uri u;
            if (value.Any(char.IsWhiteSpace) || value.Any(char.IsControl) || value.IndexOfAny(new[] { '\\', '?', '#' }) >= 0
                || !Uri.TryCreate(value, UriKind.Absolute, out u) ||
                (u.Scheme != Uri.UriSchemeHttp && u.Scheme != Uri.UriSchemeHttps) ||
                u.UserInfo.Length != 0 || u.Host.Length == 0 || u.Port == 0)
                throw new InvalidDataException("Enter a server base URL with no credentials, query, or fragment.");
            if (u.Scheme == Uri.UriSchemeHttp && !u.IsLoopback)
                throw new InvalidDataException("Remote servers require HTTPS. Plain HTTP is local only.");
            string path = u.AbsolutePath.TrimEnd('/');
            if (path.EndsWith("/api/v1/snapshot", StringComparison.OrdinalIgnoreCase) ||
                path.EndsWith("/healthz", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Enter the server base URL, without /api/v1/snapshot or /healthz.");
            return u.GetLeftPart(UriPartial.Authority) + path;
        }

        public static async Task<Snapshot> Fetch(string url, string token)
        {
            var endpoint = new Uri(Url(url) + "/api/v1/snapshot");
            if (!String.IsNullOrEmpty(token) && (token.Length > 4096 || !Bearer.IsMatch(token)))
                throw new InvalidDataException("Invalid RDR_API_TOKEN format.");
            try
            {
                using (var handler = new HttpClientHandler { AllowAutoRedirect = false, UseProxy = false, UseCookies = false })
                using (var http = new HttpClient(handler))
                using (var time = new CancellationTokenSource(TimeSpan.FromSeconds(8)))
                using (var req = new HttpRequestMessage(HttpMethod.Get, endpoint))
                {
                    req.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
                    req.Headers.UserAgent.ParseAdd("RedDeerRiver-WindowsReceiver/1.0");
                    req.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true };
                    if (!String.IsNullOrEmpty(token))
                        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
                    using (var res = await http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, time.Token).ConfigureAwait(false))
                    {
                        if (res.StatusCode != HttpStatusCode.OK)
                            throw new InvalidDataException("Service returned HTTP " + ((int)res.StatusCode).ToString(CultureInfo.InvariantCulture) + ".");
                        var mime = res.Content.Headers.ContentType;
                        if (mime == null || !String.Equals(mime.MediaType, "application/json", StringComparison.OrdinalIgnoreCase))
                            throw new InvalidDataException("Expected a JSON snapshot from the service.");
                        if (res.Content.Headers.ContentLength.GetValueOrDefault() > MaxBytes)
                            throw new InvalidDataException("The service snapshot exceeded its size limit.");
                        using (var data = await res.Content.ReadAsStreamAsync().ConfigureAwait(false))
                        using (var output = new MemoryStream())
                        {
                            byte[] buffer = new byte[8192];
                            int n;
                            while ((n = await data.ReadAsync(buffer, 0, buffer.Length, time.Token).ConfigureAwait(false)) > 0)
                            {
                                if (output.Length + n > MaxBytes)
                                    throw new InvalidDataException("The service snapshot exceeded its size limit.");
                                output.Write(buffer, 0, n);
                            }
                            return Parse(new UTF8Encoding(false, true).GetString(output.ToArray()));
                        }
                    }
                }
            }
            catch (OperationCanceledException) { throw new InvalidDataException("The service request timed out."); }
            catch (HttpRequestException) { throw new InvalidDataException("Could not reach the service. Check its URL, connection, or TLS certificate."); }
            catch (DecoderFallbackException) { throw new InvalidDataException("The service sent invalid UTF-8."); }
        }

        private static Dictionary<string, object> Dict(object obj) { return obj as Dictionary<string, object>; }
        private static object Get(Dictionary<string, object> d, string name)
        {
            object val;
            return d != null && d.TryGetValue(name, out val) ? val : null;
        }
        private static string Text(object obj, int limit = 350)
        {
            var raw = obj as string;
            if (raw == null) return "";
            string clean = String.Join(" ", new String(raw.Where(c => !char.IsControl(c) || char.IsWhiteSpace(c)).ToArray())
                .Split((char[])null, StringSplitOptions.RemoveEmptyEntries));
            return clean.Length > limit ? clean.Substring(0, limit - 1) + "…" : clean;
        }
        private static DateTimeOffset? Time(object obj)
        {
            string s = obj as string;
            DateTimeOffset dt;
            if (s != null && s.Length <= 50 && s.Contains("T") && Zone.IsMatch(s) &&
                DateTimeOffset.TryParse(s, CultureInfo.InvariantCulture, DateTimeStyles.None, out dt))
                return dt.ToUniversalTime();
            return null;
        }
        private static double? Number(object obj)
        {
            if (!(obj is int || obj is long || obj is decimal || obj is double)) return null;
            var d = Convert.ToDouble(obj, CultureInfo.InvariantCulture);
            return Double.IsNaN(d) || Double.IsInfinity(d) ? (double?)null : d;
        }
        private static Reading Read(Dictionary<string, object> row, string id, string name, string unit, bool depth)
        {
            string state = Text(Get(row, "status"));
            var val = Number(Get(row, "value"));
            var at = Time(Get(row, depth ? "valid_at" : "observed_at"));
            if (Text(Get(row, "unit")) != unit) { at = null; val = null; }
            if (depth && (Text(Get(row, "kind")) != (id == "P06" ? "terminal_stage_proxy" : "latent") ||
                (id == "P06" && Text(Get(row, "station_id")) != "05CC002"))) { val = null; at = null; }
            if (!at.HasValue || (depth ? state != "experimental" : state != "ok" && state != "stale")) val = null;
            return new Reading {
                Id = id, Title = name, Value = val, Clock = at,
                Status = val.HasValue ? (depth ? "Experimental" : state == "stale" ? "Stale" : "Available") : (depth ? "Unavailable" : "Missing"),
                Period = Text(Get(row, "period"), 70), Source = Text(Get(row, "source"), 90),
                Retrieved = Time(Get(row, "retrieved_at")), WindowEnd = Time(Get(row, "window_end_at"))
            };
        }
        private static Dictionary<string, Dictionary<string, object>> Index(object raw, string key)
        {
            var index = new Dictionary<string, Dictionary<string, object>>(StringComparer.Ordinal);
            var list = raw as object[];
            if (list == null) return index;
            foreach (var element in list)
            {
                var row = Dict(element); string id = Text(Get(row, key), 20);
                if (id.Length == 0 || index.ContainsKey(id))
                    throw new InvalidDataException("Snapshot contains a missing or duplicate identifier.");
                index[id] = row;
            }
            return index;
        }
        private static Dictionary<string, object> Find(Dictionary<string, Dictionary<string, object>> index, string key)
        {
            Dictionary<string, object> row;
            return index.TryGetValue(key, out row) ? row : null;
        }
        private static Group ReadGroup(Dictionary<string, object> block, int h, DateTimeOffset? fallback)
        {
            var info = Dict(Get(block, "inference"));
            var state = Text(Get(info, "status"));
            var target = Time(Get(info, "valid_at")) ?? fallback;
            var index = Index(Get(block, "depths"), "node_id");
            var outputs = Enumerable.Range(1, 6).Select(n =>
            {
                string id = "P" + n.ToString("00", CultureInfo.InvariantCulture);
                var estimate = Read(state == "experimental" && target.HasValue ? Find(index, id) : null, id,
                    n == 6 ? "Terminal water-depth proxy (05CC002)" : "Intermediate latent estimate (unverified)", "m", true);
                if (estimate.Value.HasValue && estimate.Clock != target)
                {
                    estimate.Value = null; estimate.Status = "Unavailable"; estimate.Clock = null;
                }
                return estimate;
            }).ToArray();
            var note = Text(Get(info, "note"));
            bool any = outputs.Any(r => r.Value.HasValue);
            if (!any)
            {
                string detail = Text(Get(Dict(Get(info, "provenance")), "unavailable_reason"), 95);
                string reason;
                if (Reasons.TryGetValue(detail, out reason)) note = reason;
                else if (note.Length == 0) note = "No qualifying upstream observations or estimate were supplied for this target.";
            }
            return new Group { Hours = h, Depths = outputs, State = any ? "Experimental" : "Unavailable",
                Target = target, Generated = Time(Get(info, "generated_at")), Note = note };
        }

        public static Snapshot Parse(string json)
        {
            Dictionary<string, object> body;
            try
            {
                body = Dict(new JavaScriptSerializer { MaxJsonLength = MaxBytes, RecursionLimit = 24 }.DeserializeObject(json));
            }
            catch (ArgumentException) { throw new InvalidDataException("Invalid snapshot JSON."); }
            catch (InvalidOperationException) { throw new InvalidDataException("Invalid snapshot JSON."); }
            var version = Get(body, "schema_version");
            var mode = Text(Get(body, "mode"));
            var status = Text(Get(body, "status"));
            var created = Time(Get(body, "generated_at"));
            if (!(version is int) || (int)version != 1 || (mode != "demo" && mode != "live") || !created.HasValue ||
                (status != "ok" && status != "partial" && status != "unavailable"))
                throw new InvalidDataException("Expected a version 1 snapshot with a valid mode, status, and UTC timestamp.");
            var flows = Index(Get(body, "flows"), "station_id");
            var rain = Dict(Get(body, "rain"));
            if (Text(Get(rain, "station_id")) != "3025484") rain = null;
            var current = ReadGroup(body, 0, null);
            var horizons = new Dictionary<int, Dictionary<string, object>>();
            foreach (var block in (Get(body, "horizons") as object[]) ?? new object[0])
            {
                var row = Dict(block); var key = Get(row, "hours");
                if (!(key is int) || ((int)key != 3 && (int)key != 9)) continue;
                int h = (int)key;
                if (horizons.ContainsKey(h)) throw new InvalidDataException("Snapshot contains a duplicate target.");
                horizons[h] = row;
            }
            var responseGroups = new[] { current }.Concat(new[] { 3, 9 }.Select(h =>
            {
                Dictionary<string, object> row;
                horizons.TryGetValue(h, out row);
                DateTimeOffset? fallback = current.Target.HasValue ? current.Target.Value.AddHours(h) : (DateTimeOffset?)null;
                return ReadGroup(row, h, fallback);
            })).ToArray();
            return new Snapshot {
                Mode = mode, State = status == "ok" ? "Available" : status == "partial" ? "Partial" : "Unavailable",
                Generated = created.Value, Warning = Text(Get(body, "warning")),
                BackendError = Text(Get(Dict(Get(body, "collection")), "internal_error")),
                Flows = Stations.Select((id, i) => Read(Find(flows, id), id, StationNames[i], "m3/s", false)).ToArray(),
                Rain = Read(rain, "3025484", "Red Deer Regional A", "mm", false),
                Groups = responseGroups
            };
        }

        public static string Clock(DateTimeOffset? time)
        {
            return time.HasValue ? time.Value.ToString("yyyy-MM-dd HH:mm:ss 'UTC'", CultureInfo.InvariantCulture) : "—";
        }

        public static string Value(double? value, int decimals)
        {
            if (!value.HasValue) return "—";
            var n = value.Value;
            var rendered = n.ToString("F" + decimals, CultureInfo.InvariantCulture);
            if (n != 0 && (Math.Abs(n) >= 1e7 || Double.Parse(rendered, CultureInfo.InvariantCulture) == 0))
                return n.ToString("G4", CultureInfo.InvariantCulture);
            return rendered;
        }
    }

    internal sealed class Viewer : Form
    {
        private static readonly Color Ink = Color.FromArgb(21, 40, 61);
        private static readonly Color Muted = Color.FromArgb(60, 78, 95);
        private static readonly Color WarningColor = Color.FromArgb(133, 45, 37);
        private static readonly Color Canvas = Color.FromArgb(246, 248, 251);
        private readonly TextBox address = new TextBox();
        private readonly Label status = LabelOf("", 10, true, Ink);
        private readonly Label clocks = LabelOf("", 9, false, Muted);
        private readonly Label notice = LabelOf("", 9, true, WarningColor);
        private readonly Label rainDetail = LabelOf("", 9, false, Muted);
        private readonly DataGridView flowGrid = Grid("Station / WSC ID", "Observation time");
        private readonly DataGridView rainGrid = Grid("Climate station", "Observation time");
        private readonly Dictionary<int, DataGridView> depthGrid = new Dictionary<int, DataGridView>();
        private readonly Dictionary<int, Label> depthDetail = new Dictionary<int, Label>();
        private readonly TabControl targets = new TabControl();
        private readonly System.Windows.Forms.Timer schedule = new System.Windows.Forms.Timer();
        private readonly string sessionToken, tokenEndpoint;
        private string server, error;
        private bool working, afterChange;
        private long generation;
        private DateTimeOffset next = DateTimeOffset.MinValue;
        private DateTimeOffset? lastContact;
        private Snapshot latest;
        internal event Action Arrived;

        public Viewer(string serverUrl, string token)
        {
            server = serverUrl; sessionToken = token; tokenEndpoint = serverUrl;
            Text = "Red Deer River | Research Receiver";
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(1080, 790);
            MinimumSize = new Size(850, 705);
            BackColor = Canvas;
            Font = new Font("Segoe UI", 9);
            AutoScaleMode = AutoScaleMode.Dpi;

            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(12, 8, 12, 8),
                ColumnCount = 1, RowCount = 9, BackColor = Canvas };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            foreach (int px in new[] { 34, 38, 36, 23, 22, 37, 133, 91 })
                layout.RowStyles.Add(new RowStyle(SizeType.Absolute, px));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            Controls.Add(layout);
            layout.Controls.Add(LabelOf("Red Deer River", 19, true, Ink), 0, 0);
            var disclaimer = LabelOf(Contract.Disclaimer, 9, true, WarningColor);
            disclaimer.BackColor = Color.FromArgb(252, 235, 229);
            disclaimer.Padding = new Padding(7, 2, 7, 2);
            layout.Controls.Add(disclaimer, 0, 1);

            var control = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 4, RowCount = 1 };
            control.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 105));
            control.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            control.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 87));
            control.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 105));
            control.Controls.Add(LabelOf("Server base URL", 9, true, Ink), 0, 0);
            address.Text = server;
            address.Dock = DockStyle.Fill;
            address.Margin = new Padding(3, 6, 3, 2);
            address.AccessibleName = "Server base URL";
            address.KeyDown += delegate(object sender, KeyEventArgs evt)
            {
                if (evt.KeyCode == Keys.Enter) { evt.SuppressKeyPress = true; Reconnect(); }
            };
            control.Controls.Add(address, 1, 0);
            var connect = new Button { Text = "Connect", Dock = DockStyle.Fill };
            connect.Click += delegate { Reconnect(); };
            control.Controls.Add(connect, 2, 0);
            var refresh = new Button { Text = "Refresh now", Dock = DockStyle.Fill };
            refresh.Click += delegate { if (!working) { next = DateTimeOffset.MinValue; Poll(); } };
            control.Controls.Add(refresh, 3, 0);
            layout.Controls.Add(control, 0, 2);
            layout.Controls.Add(status, 0, 3);
            layout.Controls.Add(clocks, 0, 4);
            layout.Controls.Add(notice, 0, 5);
            layout.Controls.Add(Box("Observed river discharge (m³/s)", flowGrid, null), 0, 6);
            layout.Controls.Add(Box("Regional airport precipitation (mm), not basin rainfall", rainGrid, rainDetail), 0, 7);
            targets.Dock = DockStyle.Fill;
            targets.Margin = new Padding(2);
            targets.AccessibleName = "Water-depth estimate target";
            layout.Controls.Add(targets, 0, 8);
            foreach (var h in new[] { 0, 3, 9 })
            {
                var page = new TabPage(h == 0 ? "Current time" : "+" + h + " hours");
                page.BackColor = Canvas;
                var content = new TableLayoutPanel { ColumnCount = 1, RowCount = 4, Dock = DockStyle.Fill, Padding = new Padding(4) };
                content.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
                content.RowStyles.Add(new RowStyle(SizeType.Absolute, 23));
                content.RowStyles.Add(new RowStyle(SizeType.Absolute, 53));
                content.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
                content.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
                var title = h == 0 ? "Estimated depth at current target time (m)" :
                    "Experimental depth at the +" + h + "-hour target (m)";
                content.Controls.Add(LabelOf(title, 10, true, Ink), 0, 0);
                var detail = LabelOf("", 9, false, Muted);
                depthDetail[h] = detail;
                content.Controls.Add(detail, 0, 1);
                var grid = Grid("Node / interpretation", "Model valid time");
                depthGrid[h] = grid;
                content.Controls.Add(grid, 0, 2);
                content.Controls.Add(LabelOf(Contract.Limit, 9, false, Muted), 0, 3);
                page.Controls.Add(content);
                targets.TabPages.Add(page);
            }
            schedule.Interval = 800;
            schedule.Tick += delegate { if (!working && DateTimeOffset.UtcNow >= next) Poll(); };
            Shown += delegate { schedule.Start(); Poll(); };
            FormClosed += delegate { schedule.Stop(); schedule.Dispose(); };
            Render();
        }

        private static Label LabelOf(string text, float points, bool bold, Color color)
        {
            return new Label { Text = text, Dock = DockStyle.Fill, Margin = new Padding(1),
                Font = new Font("Segoe UI", points, bold ? FontStyle.Bold : FontStyle.Regular),
                ForeColor = color, TextAlign = ContentAlignment.MiddleLeft, UseMnemonic = false };
        }

        private static Control Box(string title, Control centre, Control extra)
        {
            var outer = new GroupBox { Dock = DockStyle.Fill, Text = title, ForeColor = Ink, Margin = new Padding(1, 2, 1, 3) };
            var body = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = extra == null ? 1 : 2 };
            body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            body.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            body.Controls.Add(centre, 0, 0);
            if (extra != null)
            {
                body.RowStyles.Add(new RowStyle(SizeType.Absolute, 22));
                body.Controls.Add(extra, 0, 1);
            }
            outer.Controls.Add(body);
            return outer;
        }

        private static DataGridView Grid(string first, string clock)
        {
            var grid = new DataGridView {
                Dock = DockStyle.Fill, Margin = new Padding(0), ReadOnly = true, RowHeadersVisible = false,
                AllowUserToAddRows = false, AllowUserToDeleteRows = false, AllowUserToOrderColumns = false,
                AllowUserToResizeRows = false, BackgroundColor = Color.White, BorderStyle = BorderStyle.FixedSingle,
                CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal, GridColor = Color.FromArgb(222, 230, 237),
                MultiSelect = false, SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill, ColumnHeadersHeight = 25,
                ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.DisableResizing,
                EnableHeadersVisualStyles = false, AccessibleName = first
            };
            grid.RowTemplate.Height = 19;
            grid.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(228, 236, 244);
            grid.ColumnHeadersDefaultCellStyle.ForeColor = Ink;
            grid.DefaultCellStyle.ForeColor = Ink;
            grid.AlternatingRowsDefaultCellStyle.BackColor = Color.FromArgb(245, 248, 251);
            string[] labels = { first, "Value", "Status", clock };
            float[] shares = { 46, 10, 17, 27 };
            for (int i = 0; i < labels.Length; i++)
            {
                var col = new DataGridViewTextBoxColumn { Name = "c" + i, HeaderText = labels[i],
                    FillWeight = shares[i], SortMode = DataGridViewColumnSortMode.NotSortable };
                col.MinimumWidth = i == 3 ? 162 : i == 2 ? 112 : 60;
                if (i == 1) col.DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleRight;
                grid.Columns.Add(col);
            }
            return grid;
        }

        private void Reconnect()
        {
            string url;
            try { url = Contract.Url(address.Text); }
            catch (InvalidDataException e)
            {
                MessageBox.Show(this, e.Message, "Check the server URL", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            address.Text = url;
            if (url != server)
            {
                server = url; generation++;
                latest = null; lastContact = null; error = null;
                afterChange = working;
            }
            next = DateTimeOffset.MinValue;
            Render();
            if (!working) Poll();
        }

        private async void Poll()
        {
            if (working || IsDisposed) return;
            working = true;
            long forGeneration = generation;
            var url = server;
            next = DateTimeOffset.UtcNow.AddSeconds(60);
            Render();
            Snapshot candidate = null;
            string failure = null;
            try
            {
                candidate = await Contract.Fetch(url, url == tokenEndpoint ? sessionToken : null);
            }
            catch (InvalidDataException e) { failure = e.Message; }
            catch (Exception) { failure = "The service connection failed. Check the server and try again."; }
            if (IsDisposed) return;
            working = false;
            if (forGeneration == generation)
            {
                error = failure;
                if (candidate != null) { latest = candidate; lastContact = DateTimeOffset.UtcNow; }
                Render();
                var listener = Arrived;
                if (candidate != null && listener != null) listener();
            }
            if (afterChange && !IsDisposed)
            {
                afterChange = false;
                Poll();
            }
        }

        private static void Fill(DataGridView grid, IEnumerable<Reading> rows, int precision, bool cached)
        {
            grid.Rows.Clear();
            foreach (var r in rows)
            {
                var state = cached && r.Value.HasValue ? "Cached / " + r.Status : r.Status;
                int index = grid.Rows.Add(r.Id + "   " + r.Title, Contract.Value(r.Value, precision), state, Contract.Clock(r.Clock));
                if (state.StartsWith("Cached", StringComparison.Ordinal) || r.Status == "Stale")
                    grid.Rows[index].Cells[2].Style.ForeColor = WarningColor;
            }
            grid.ClearSelection();
        }

        private void Render()
        {
            var snap = latest;
            bool old = snap != null && (DateTimeOffset.UtcNow - snap.Generated > TimeSpan.FromMinutes(125) || snap.BackendError == "cached_snapshot_stale");
            bool cached = snap != null && (old || error != null || snap.BackendError == "database_unavailable");
            string mode = snap == null ? "Unknown mode" : snap.Mode == "demo" ? "DEMO: synthetic inputs" : "LIVE: provider observations";
            string network = error != null ? "Connection failed" : old ? "Old server snapshot" :
                cached ? "Server cache" : working ? "Refreshing" : lastContact.HasValue ? "Connected" : "Waiting";
            status.Text = mode + "   |   Service: " + (snap == null ? "No snapshot" : snap.State) + "   |   " + network + "   |   Poll: 60 s";
            clocks.Text = "Newest observation: " + Contract.Clock(snap == null ? null : snap.Newest) +
                "  |  Snapshot: " + Contract.Clock(snap == null ? null : (DateTimeOffset?)snap.Generated) +
                "  |  Last contact: " + Contract.Clock(lastContact);
            notice.Text = error != null ? error + (cached ? " Showing cached values, not current data." : " No values available.") :
                old ? "Showing cached values, not current data. The server snapshot is not recent." :
                cached ? "Showing cached values, not current data. The server data store is unavailable." : snap == null ? "" : snap.Warning;

            var shown = snap ?? EmptySnapshot.Value;
            Fill(flowGrid, shown.Flows, 2, cached);
            Fill(rainGrid, new[] { shown.Rain }, 2, cached);
            var rain = shown.Rain;
            rainDetail.Text = "Source: " + (String.IsNullOrEmpty(rain.Source) ? "Not reported" : rain.Source) +
                "  |  Period: " + (String.IsNullOrEmpty(rain.Period) ? "Not reported" : rain.Period) +
                "  |  Period end: " + Contract.Clock(rain.WindowEnd) + "  |  Retrieved: " + Contract.Clock(rain.Retrieved);
            foreach (var g in shown.Groups)
            {
                Fill(depthGrid[g.Hours], g.Depths, 3, cached);
                depthDetail[g.Hours].Text = "Inference: " + (cached && g.State == "Experimental" ? "Cached / " : "") + g.State +
                    "  |  Target time: " + Contract.Clock(g.Target) +
                    "  |  Generated: " + Contract.Clock(g.Generated) +
                    Environment.NewLine + (String.IsNullOrEmpty(g.Note) ? "Estimates are not gauge measurements." : g.Note);
            }
        }

        private static readonly Lazy<Snapshot> EmptySnapshot = new Lazy<Snapshot>(delegate
        {
            return Contract.Parse("{\"schema_version\":1,\"mode\":\"demo\",\"status\":\"unavailable\",\"generated_at\":\"2000-01-01T00:00:00Z\",\"flows\":[],\"depths\":[],\"horizons\":[]}");
        });

        internal bool SmokeReconnect(string nextUrl)
        {
            address.Text = nextUrl;
            Reconnect();
            return latest == null && working &&
                Convert.ToString(flowGrid.Rows[0].Cells[1].Value) == "—";
        }

        internal bool SmokeCheck(string expected)
        {
            if (latest == null || latest.Mode != "demo" || !status.Text.StartsWith("DEMO:", StringComparison.Ordinal)) return false;
            if (!targets.TabPages.Cast<TabPage>().Select(p => p.Text).SequenceEqual(new[] { "Current time", "+3 hours", "+9 hours" }))
                return false;
            if (latest.Flows.Count(q => q.Value.HasValue) != 4 || !latest.Rain.Value.HasValue ||
                String.IsNullOrEmpty(latest.Rain.Period) || String.IsNullOrEmpty(latest.Rain.Source)) return false;
            if (flowGrid.Rows.Count != 4 || rainGrid.Rows.Count != 1) return false;
            if (latest.Groups[1].Target - latest.Groups[0].Target != TimeSpan.FromHours(3) ||
                latest.Groups[2].Target - latest.Groups[0].Target != TimeSpan.FromHours(9)) return false;
            var hits = latest.Groups.Select(g => g.Depths.Count(p => p.Value.HasValue)).ToArray();
            if (hits[0] != 6 || hits[1] != 6) return false;
            if (expected == "complete")
                return hits[2] == 6 && depthDetail[9].Text.Contains("Experimental") &&
                    Convert.ToString(depthGrid[9].Rows[5].Cells[1].Value) != "—";
            return expected == "partial" && hits[2] == 0 && depthDetail[9].Text.Contains("Unavailable") &&
                depthDetail[9].Text.Contains("Little Red Deer River") &&
                Convert.ToString(depthGrid[9].Rows[5].Cells[1].Value) == "—";
        }
    }

    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            ServicePointManager.SecurityProtocol = SecurityProtocolType.SystemDefault;
            bool switching = args.Length == 3 && args[0] == "--smoke-switch";
            bool smoke = switching || (args.Length == 3 && args[0] == "--smoke-test");
            if (smoke)
            {
                try
                {
                    if (Contract.Url("https://host.example:8443") != "https://host.example:8443" ||
                        Contract.Url("https://host.example") != "https://host.example" ||
                        Contract.Url("http://127.0.0.1:8765/") != Contract.DefaultUrl) return 7;
                    try { Contract.Url("http://host.example:8443"); return 7; }
                    catch (InvalidDataException) { }
                }
                catch (InvalidDataException) { return 7; }
            }
            string supplied = smoke ? args[1] : args.Length == 2 && args[0] == "--server" ? args[1] :
                Environment.GetEnvironmentVariable("RDR_SERVER_URL");
            string url;
            try { url = Contract.Url(String.IsNullOrWhiteSpace(supplied) ? Contract.DefaultUrl : supplied); }
            catch (InvalidDataException e)
            {
                if (!smoke) MessageBox.Show(e.Message, "Check the default server URL", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return 1;
            }
            string token = smoke ? null : Environment.GetEnvironmentVariable("RDR_API_TOKEN");
            using (var viewer = new Viewer(url, token))
            {
                if (!smoke) { Application.Run(viewer); return 0; }
                viewer.ShowInTaskbar = false;
                viewer.Opacity = 0;
                using (var deadline = new System.Windows.Forms.Timer { Interval = 13000 })
                {
                    int result = 5;
                    deadline.Tick += delegate { deadline.Stop(); viewer.Close(); };
                    viewer.Shown += delegate { deadline.Start(); };
                    bool second = false;
                    viewer.Arrived += delegate
                    {
                        if (switching && !second)
                        {
                            if (!viewer.SmokeCheck("complete")) { result = 6; viewer.Close(); return; }
                            second = true;
                            try
                            {
                                if (viewer.SmokeReconnect(Contract.Url(args[2]))) return;
                            }
                            catch (InvalidDataException) { }
                            result = 8; viewer.Close(); return;
                        }
                        result = viewer.SmokeCheck(switching ? "partial" : args[2]) ? 0 : 9;
                        viewer.Close();
                    };
                    Application.Run(viewer);
                    return result;
                }
            }
        }
    }
}

