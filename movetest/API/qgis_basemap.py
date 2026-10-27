"""Provide standard OpenStreetMap XYZ tiles for a requested QGIS view.

QGIS handles viewport requests and its normal HTTP cache. This module provides
no tile enumeration, prefetch, offline archive or acquisition scheduler.
"""

from urllib.parse import quote

OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "RedDeerRiverMap/1.0 (QGIS; https://github.com/silviaprrsh-cyber/2026-Fall-AIDA-Final-Project)"


def create_osm_layer():
    """Call from the installed QGIS runtime for user-requested mapping."""
    from qgis.core import QgsNetworkAccessManager, QgsRasterLayer
    from qgis.PyQt.QtNetwork import QNetworkRequest

    diagnostics = {"requested_urls": set(), "responses": []}

    def identify(request):
        if request.url().host() == "tile.openstreetmap.org":
            request.setRawHeader(b"User-Agent", USER_AGENT.encode("ascii"))
            diagnostics["requested_urls"].add(request.url().toString())

    def observe(request, reply):
        if request.url().host() != "tile.openstreetmap.org":
            return

        def finished():
            diagnostics["responses"].append({
                "status": reply.attribute(QNetworkRequest.HttpStatusCodeAttribute),
                "from_cache": bool(reply.attribute(QNetworkRequest.SourceIsFromCacheAttribute)),
                "error": int(reply.error()),
                "error_message": reply.errorString() if reply.error() else None,
            })

        reply.finished.connect(finished)

    request_hook = QgsNetworkAccessManager.setRequestPreprocessor(identify)
    reply_hook = QgsNetworkAccessManager.setReplyPreprocessor(observe)
    QgsNetworkAccessManager.setTimeout(20000)
    uri = "type=xyz&url=" + quote(OSM_URL, safe=":/") + "&zmin=0&zmax=19&crs=EPSG3857"
    uri += "&http-header:user-agent=" + quote(USER_AGENT, safe="")
    layer = QgsRasterLayer(uri, "OpenStreetMap", "wms")
    if not layer.isValid():
        raise RuntimeError("QGIS could not initialize the OpenStreetMap XYZ provider")
    metadata = layer.metadata()
    metadata.setTitle("OpenStreetMap")
    metadata.setRights(["© OpenStreetMap contributors; https://www.openstreetmap.org/copyright"])
    metadata.setAbstract("Standard OpenStreetMap XYZ basemap. Internet required. https://operations.osmfoundation.org/policies/tiles/")
    layer.setMetadata(metadata)
    layer.setAttribution("© OpenStreetMap contributors")
    layer.setAttributionUrl("https://www.openstreetmap.org/copyright")
    return layer, diagnostics, (request_hook, reply_hook)
