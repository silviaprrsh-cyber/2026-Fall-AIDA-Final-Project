// Red Deer River Hydro-GIS read-only research receiver for Windows (.NET Framework 4.8 + WebView2).
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

[assembly: AssemblyTitle("Red Deer River Hydro-GIS Research Receiver")]
[assembly: AssemblyProduct("AIDA 2156/2362 Red Deer River Hydro-GIS Course Demo")]
[assembly: AssemblyVersion("2.1.0.0")]
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
        private const int MaxBytes = 128 * 1024;
        private const int MaxHistoryBytes = 512 * 1024;
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
                path.EndsWith("/api/v1/history48h", StringComparison.OrdinalIgnoreCase) ||
                path.EndsWith("/healthz", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Enter the server base URL, without /api/v1/snapshot or /healthz.");
            return u.GetLeftPart(UriPartial.Authority) + path;
        }

        private static async Task<string> FetchJson(Uri endpoint, string token, int maxBytes)
        {
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
                    req.Headers.UserAgent.ParseAdd("RedDeerRiver-HydroGISReceiver/2.1");
                    req.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true };
                    if (!String.IsNullOrEmpty(token))
                        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
                    using (var res = await http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, time.Token).ConfigureAwait(false))
                    {
                        if (res.StatusCode != HttpStatusCode.OK)
                            throw new InvalidDataException("Service returned HTTP " + ((int)res.StatusCode).ToString(CultureInfo.InvariantCulture) + ".");
                        var mime = res.Content.Headers.ContentType;
                        if (mime == null || !String.Equals(mime.MediaType, "application/json", StringComparison.OrdinalIgnoreCase))
                            throw new InvalidDataException("Expected a JSON response from the service.");
                        if (res.Content.Headers.ContentLength.GetValueOrDefault() > maxBytes)
                            throw new InvalidDataException("The service response exceeded its size limit.");
                        using (var data = await res.Content.ReadAsStreamAsync().ConfigureAwait(false))
                        using (var output = new MemoryStream())
                        {
                            byte[] buffer = new byte[8192];
                            int n;
                            while ((n = await data.ReadAsync(buffer, 0, buffer.Length, time.Token).ConfigureAwait(false)) > 0)
                            {
                                if (output.Length + n > maxBytes)
                                    throw new InvalidDataException("The service response exceeded its size limit.");
                                output.Write(buffer, 0, n);
                            }
                            return new UTF8Encoding(false, true).GetString(output.ToArray());
                        }
                    }
                }
            }
            catch (OperationCanceledException) { throw new InvalidDataException("The service request timed out."); }
            catch (HttpRequestException) { throw new InvalidDataException("Could not reach the service. Check its URL, connection, or TLS certificate."); }
            catch (DecoderFallbackException) { throw new InvalidDataException("The service sent invalid UTF-8."); }
        }

        public static async Task<Snapshot> Fetch(string url, string token)
        {
            string raw = await FetchJson(new Uri(Url(url) + "/api/v1/snapshot"), token, MaxBytes).ConfigureAwait(false);
            return Parse(raw);
        }

        public static async Task<object> FetchHistory48h(string url, string token)
        {
            try
            {
                string raw = await FetchJson(new Uri(Url(url) + "/api/v1/history48h"), token, MaxHistoryBytes).ConfigureAwait(false);
                return new JavaScriptSerializer { MaxJsonLength = MaxHistoryBytes, RecursionLimit = 24 }.DeserializeObject(raw);
            }
            catch { return null; }
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
            return new Reading
            {
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
            return new Group
            {
                Hours = h, Depths = outputs, State = any ? "Experimental" : "Unavailable",
                Target = target, Generated = Time(Get(info, "generated_at")), Note = note
            };
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
            return new Snapshot
            {
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

        public static bool SmokeValidate(Snapshot snap, string expected)
        {
            if (snap == null || snap.Mode != "demo") return false;
            if (snap.Flows.Count(q => q.Value.HasValue) != 4 || !snap.Rain.Value.HasValue ||
                String.IsNullOrEmpty(snap.Rain.Period) || String.IsNullOrEmpty(snap.Rain.Source)) return false;
            if (snap.Groups.Length != 3) return false;
            if (snap.Groups[1].Target - snap.Groups[0].Target != TimeSpan.FromHours(3) ||
                snap.Groups[2].Target - snap.Groups[0].Target != TimeSpan.FromHours(9)) return false;
            var hits = snap.Groups.Select(g => g.Depths.Count(p => p.Value.HasValue)).ToArray();
            if (hits[0] != 6 || hits[1] != 6) return false;
            if (expected == "complete")
                return hits[2] == 6 && snap.Groups[2].State == "Experimental" && snap.Groups[2].Depths[5].Value.HasValue;
            return expected == "partial" && hits[2] == 0 && snap.Groups[2].State == "Unavailable" &&
                (snap.Groups[2].Note ?? "").Contains("Little Red Deer River") && !snap.Groups[2].Depths[5].Value.HasValue;
        }
    }

    internal static class EmbeddedAssets
    {
        public static byte[] ReadRawBytes(string resourceName)
        {
            var asm = Assembly.GetExecutingAssembly();
            using (var stream = asm.GetManifestResourceStream(resourceName))
            {
                if (stream == null) throw new InvalidOperationException("Missing embedded resource: " + resourceName);
                using (var ms = new MemoryStream()) { stream.CopyTo(ms); return ms.ToArray(); }
            }
        }

        public static byte[] ReadGzipBytes(string resourceName)
        {
            var asm = Assembly.GetExecutingAssembly();
            using (var stream = asm.GetManifestResourceStream(resourceName))
            {
                if (stream == null) throw new InvalidOperationException("Missing embedded resource: " + resourceName);
                using (var gz = new GZipStream(stream, CompressionMode.Decompress))
                using (var ms = new MemoryStream())
                {
                    gz.CopyTo(ms);
                    return ms.ToArray();
                }
            }
        }
    }

    internal static class WebViewBootstrap
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr LoadLibrary(string lpFileName);

        [DllImport("user32.dll")]
        private static extern bool SetProcessDPIAware();

        private static string _libDir;
        private static string _assetsDir;
        private static bool _initialized;

        public static string AssetsDir { get { return _assetsDir; } }

        public static string UserDataDir
        {
            get
            {
                string dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "RedDeerRiver", "WebView2Data");
                Directory.CreateDirectory(dir);
                return dir;
            }
        }

        public static void Init()
        {
            if (_initialized) return;
            try { SetProcessDPIAware(); } catch { }
            string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "RedDeerRiver");
            _libDir = Path.Combine(root, "wv2-1.0.2903.40");
            _assetsDir = Path.Combine(root, "ui-assets-2.3");
            Directory.CreateDirectory(_libDir);
            Directory.CreateDirectory(_assetsDir);

            ExtractGzip("wv2_loader.dll.gz", Path.Combine(_libDir, "WebView2Loader.dll"));
            ExtractGzip("wv2_core.dll.gz", Path.Combine(_libDir, "Microsoft.Web.WebView2.Core.dll"));
            ExtractGzip("wv2_winforms.dll.gz", Path.Combine(_libDir, "Microsoft.Web.WebView2.WinForms.dll"));

            // Unpack UI + GIS + Replay + OGL-Canada Alberta & Reach Basemaps for clean HTTPS virtual-host serving
            ExtractGzipAlways("ui.html.gz", Path.Combine(_assetsDir, "ui.html"));
            ExtractGzipAlways("gis_bundle.json.gz", Path.Combine(_assetsDir, "gis_bundle.json"));
            ExtractGzipAlways("replay_history.json.gz", Path.Combine(_assetsDir, "replay_history.json"));
            ExtractGzipAlways("nrcan_cbmt_basemap.json.gz", Path.Combine(_assetsDir, "nrcan_cbmt_basemap.json"));
            ExtractRaw("nrcan_cbmt_basemap.jpg", Path.Combine(_assetsDir, "nrcan_cbmt_basemap.jpg"));
            ExtractGzipAlways("nrcan_ab_wide.json.gz", Path.Combine(_assetsDir, "nrcan_ab_wide.json"));
            ExtractRaw("nrcan_ab_wide.jpg", Path.Combine(_assetsDir, "nrcan_ab_wide.jpg"));

            LoadLibrary(Path.Combine(_libDir, "WebView2Loader.dll"));
            AppDomain.CurrentDomain.AssemblyResolve += OnResolve;
            _initialized = true;
        }

        private static void ExtractGzip(string resName, string destPath)
        {
            byte[] data = EmbeddedAssets.ReadGzipBytes(resName);
            if (File.Exists(destPath) && new FileInfo(destPath).Length == data.Length) return;
            try { File.WriteAllBytes(destPath, data); }
            catch (IOException) { if (!File.Exists(destPath)) throw; }
        }

        private static void ExtractGzipAlways(string resName, string destPath)
        {
            byte[] data = EmbeddedAssets.ReadGzipBytes(resName);
            try { File.WriteAllBytes(destPath, data); }
            catch (IOException) { if (!File.Exists(destPath)) throw; }
        }

        private static void ExtractRaw(string resName, string destPath)
        {
            byte[] data = EmbeddedAssets.ReadRawBytes(resName);
            if (File.Exists(destPath) && new FileInfo(destPath).Length == data.Length) return;
            try { File.WriteAllBytes(destPath, data); }
            catch (IOException) { if (!File.Exists(destPath)) throw; }
        }

        private static Assembly OnResolve(object sender, ResolveEventArgs args)
        {
            string shortName = new AssemblyName(args.Name).Name;
            if (shortName == "Microsoft.Web.WebView2.Core" || shortName == "Microsoft.Web.WebView2.WinForms")
            {
                string path = Path.Combine(_libDir, shortName + ".dll");
                if (File.Exists(path)) return Assembly.LoadFrom(path);
            }
            return null;
        }
    }

    internal sealed class WebViewerForm : Form
    {
        private readonly WebView2 webView = new WebView2();
        private readonly System.Windows.Forms.Timer ticker = new System.Windows.Forms.Timer();
        private readonly JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = 8 * 1024 * 1024 };
        private readonly string sessionToken, tokenEndpoint;
        private string server, error;
        private bool working, afterChange, uiReady, firstLiveSwitchDone;
        private long generation;
        private DateTimeOffset nextPoll = DateTimeOffset.MinValue;
        private DateTimeOffset? lastContact;
        private Snapshot latest;
        private object latestHistory48h;

        public WebViewerForm(string serverUrl, string token)
        {
            server = serverUrl;
            sessionToken = token;
            tokenEndpoint = serverUrl;
            Text = "Red Deer River · Hydro-GIS Research Receiver";
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(1340, 820);
            MinimumSize = new Size(960, 640);
            BackColor = Color.FromArgb(8, 13, 24);
            webView.Dock = DockStyle.Fill;
            webView.DefaultBackgroundColor = Color.FromArgb(8, 13, 24);
            Controls.Add(webView);

            ticker.Interval = 1000;
            ticker.Tick += OnTick;
            Shown += OnShownAsync;
            FormClosed += delegate { ticker.Stop(); ticker.Dispose(); };
        }

        private async void OnShownAsync(object sender, EventArgs e)
        {
            try
            {
                var env = await CoreWebView2Environment.CreateAsync(null, WebViewBootstrap.UserDataDir);
                await webView.EnsureCoreWebView2Async(env);
                webView.CoreWebView2.Settings.IsStatusBarEnabled = false;
                webView.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
                webView.CoreWebView2.SetVirtualHostNameToFolderMapping(
                    "appassets.local", WebViewBootstrap.AssetsDir, CoreWebView2HostResourceAccessKind.Allow);
                webView.CoreWebView2.WebMessageReceived += OnWebMessage;
                webView.Source = new Uri("https://appassets.local/ui.html");
                ticker.Start();
            }
            catch (Exception ex)
            {
                MessageBox.Show(this,
                    "Could not initialize Microsoft Edge WebView2 Runtime.\n\nDetails: " + ex.Message,
                    "Red Deer River Hydro-GIS", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OnWebMessage(object sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            try
            {
                var msg = json.DeserializeObject(e.WebMessageAsJson) as Dictionary<string, object>;
                if (msg == null || !msg.ContainsKey("action")) return;
                string action = Convert.ToString(msg["action"], CultureInfo.InvariantCulture);
                if (action == "ready")
                {
                    uiReady = true;
                    PushState(null);
                    Poll();
                }
                else if (action == "connect")
                {
                    string rawUrl = msg.ContainsKey("url") ? Convert.ToString(msg["url"], CultureInfo.InvariantCulture) : "";
                    Reconnect(rawUrl);
                }
                else if (action == "refresh")
                {
                    if (!working) { nextPoll = DateTimeOffset.MinValue; Poll(); }
                }
            }
            catch { }
        }

        private void OnTick(object sender, EventArgs e)
        {
            if (IsDisposed) return;
            if (!working && DateTimeOffset.UtcNow >= nextPoll)
            {
                Poll();
            }
            else if (uiReady && webView.CoreWebView2 != null)
            {
                int rem = Math.Max(0, (int)Math.Ceiling((nextPoll - DateTimeOffset.UtcNow).TotalSeconds));
                webView.CoreWebView2.PostWebMessageAsJson("{\"type\":\"tick\",\"seconds\":" + rem.ToString(CultureInfo.InvariantCulture) + "}");
            }
        }

        private void Reconnect(string rawUrl)
        {
            string url;
            try { url = Contract.Url(rawUrl); }
            catch (InvalidDataException ex)
            {
                error = ex.Message;
                PushState(null);
                return;
            }
            if (url != server)
            {
                server = url; generation++;
                latest = null; latestHistory48h = null; lastContact = null; error = null;
                firstLiveSwitchDone = false;
                afterChange = working;
            }
            else
            {
                error = null;
            }
            nextPoll = DateTimeOffset.MinValue;
            PushState(null);
            if (!working) Poll();
        }

        private async void Poll()
        {
            if (working || IsDisposed) return;
            working = true;
            long forGen = generation;
            string url = server;
            string tok = url == tokenEndpoint ? sessionToken : null;
            nextPoll = DateTimeOffset.UtcNow.AddSeconds(60);
            PushState(null);
            Snapshot candidate = null;
            object hist48 = null;
            string failure = null;
            try
            {
                candidate = await Contract.Fetch(url, tok);
                hist48 = await Contract.FetchHistory48h(url, tok);
            }
            catch (InvalidDataException ex) { failure = ex.Message; }
            catch (Exception) { failure = "The service connection failed. Check the server and try again."; }
            if (IsDisposed) return;
            working = false;
            if (forGen == generation)
            {
                error = failure;
                string autoMode = null;
                if (candidate != null)
                {
                    latest = candidate;
                    if (hist48 != null) latestHistory48h = hist48;
                    lastContact = DateTimeOffset.UtcNow;
                    if (!firstLiveSwitchDone)
                    {
                        firstLiveSwitchDone = true;
                        autoMode = candidate.Mode;
                    }
                }
                PushState(autoMode);
            }
            if (afterChange && !IsDisposed)
            {
                afterChange = false;
                Poll();
            }
        }

        private void PushState(string autoSwitchMode)
        {
            if (!uiReady || IsDisposed || webView.CoreWebView2 == null) return;
            var snap = latest;
            bool old = snap != null && (DateTimeOffset.UtcNow - snap.Generated > TimeSpan.FromMinutes(125) || snap.BackendError == "cached_snapshot_stale");
            bool cached = snap != null && (old || error != null || snap.BackendError == "database_unavailable");

            object snapObj = null;
            if (snap != null)
            {
                snapObj = new
                {
                    mode = snap.Mode,
                    state = snap.State,
                    cached = cached,
                    warning = snap.Warning,
                    newest = Contract.Clock(snap.Newest),
                    generated = Contract.Clock(snap.Generated),
                    flows = snap.Flows.Select(r => new
                    {
                        id = r.Id, title = r.Title, value = r.Value, status = r.Status, clock = Contract.Clock(r.Clock)
                    }).ToArray(),
                    rain = new
                    {
                        id = snap.Rain.Id, title = snap.Rain.Title, value = snap.Rain.Value,
                        status = snap.Rain.Status, period = snap.Rain.Period, source = snap.Rain.Source,
                        clock = Contract.Clock(snap.Rain.Clock)
                    },
                    groups = snap.Groups.Select(g => new
                    {
                        hours = g.Hours, state = g.State, note = g.Note,
                        target = Contract.Clock(g.Target), generated = Contract.Clock(g.Generated),
                        depths = g.Depths.Select(d => new
                        {
                            id = d.Id, title = d.Title, value = d.Value, status = d.Status, clock = Contract.Clock(d.Clock)
                        }).ToArray()
                    }).ToArray()
                };
            }

            var payload = new
            {
                type = "state",
                serverUrl = server,
                working = working,
                error = error,
                lastContact = Contract.Clock(lastContact),
                autoSwitchMode = autoSwitchMode,
                snapshot = snapObj,
                history48h = latestHistory48h
            };
            webView.CoreWebView2.PostWebMessageAsJson(json.Serialize(payload));
        }
    }

    internal static class Program
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        private static int RunGui(string url, string token)
        {
            using (var viewer = new WebViewerForm(url, token))
            {
                Application.Run(viewer);
                return 0;
            }
        }

        private static int RunSmoke(string[] args, bool switching)
        {
            try
            {
                if (Contract.Url("https://host.example:8443") != "https://host.example:8443" ||
                    Contract.Url("https://host.example") != "https://host.example" ||
                    Contract.Url("http://127.0.0.1:8765/") != Contract.DefaultUrl) return 7;
                try { Contract.Url("http://host.example:8443"); return 7; }
                catch (InvalidDataException) { }

                // Verify all embedded assets unpack cleanly
                string html = Encoding.UTF8.GetString(EmbeddedAssets.ReadGzipBytes("ui.html.gz"));
                string gis = Encoding.UTF8.GetString(EmbeddedAssets.ReadGzipBytes("gis_bundle.json.gz"));
                string rep = Encoding.UTF8.GetString(EmbeddedAssets.ReadGzipBytes("replay_history.json.gz"));
                byte[] bm = EmbeddedAssets.ReadRawBytes("nrcan_cbmt_basemap.jpg");
                byte[] ab = EmbeddedAssets.ReadRawBytes("nrcan_ab_wide.jpg");
                if (!html.Contains("replaySlider") || !gis.Contains("05CC002") || !rep.Contains("span_start") || bm.Length < 100000 || ab.Length < 50000) return 4;
                if (EmbeddedAssets.ReadGzipBytes("wv2_loader.dll.gz").Length < 50000) return 4;
                if (EmbeddedAssets.ReadGzipBytes("wv2_core.dll.gz").Length < 100000) return 4;
                if (EmbeddedAssets.ReadGzipBytes("wv2_winforms.dll.gz").Length < 10000) return 4;

                string u1 = Contract.Url(args[1]);
                Snapshot s1 = Contract.Fetch(u1, null).GetAwaiter().GetResult();
                object h1 = Contract.FetchHistory48h(u1, null).GetAwaiter().GetResult();
                if (h1 == null) return 3;
                if (switching)
                {
                    if (!Contract.SmokeValidate(s1, "complete")) return 6;
                    string u2 = Contract.Url(args[2]);
                    Snapshot s2 = Contract.Fetch(u2, null).GetAwaiter().GetResult();
                    return Contract.SmokeValidate(s2, "partial") ? 0 : 9;
                }
                return Contract.SmokeValidate(s1, args[2]) ? 0 : 9;
            }
            catch (Exception)
            {
                return 5;
            }
        }

        [STAThread]
        private static int Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            ServicePointManager.SecurityProtocol = SecurityProtocolType.SystemDefault;

            bool switching = args.Length == 3 && args[0] == "--smoke-switch";
            bool smoke = switching || (args.Length == 3 && args[0] == "--smoke-test");
            if (smoke) return RunSmoke(args, switching);

            string supplied = args.Length == 2 && args[0] == "--server" ? args[1] :
                Environment.GetEnvironmentVariable("RDR_SERVER_URL");
            string url;
            try { url = Contract.Url(String.IsNullOrWhiteSpace(supplied) ? Contract.DefaultUrl : supplied); }
            catch (InvalidDataException e)
            {
                MessageBox.Show(e.Message, "Check the default server URL", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return 1;
            }
            string token = Environment.GetEnvironmentVariable("RDR_API_TOKEN");
            WebViewBootstrap.Init();
            return RunGui(url, token);
        }
    }
}
