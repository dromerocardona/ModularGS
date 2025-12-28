import sys
import os
from PyQt5 import QtWidgets, QtCore, QtWebEngineWidgets
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject

class GPSMap(QWidget, QObject):

    location_updated = QtCore.pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.setMinimumSize(600, 600)

        # Create a QWidget as the window
        self.win = QtWidgets.QWidget()
        self.win.setWindowTitle("GPS Map")
        self.layout = QtWidgets.QVBoxLayout()
        self.win.setLayout(self.layout)

        # QWebEngineView to display the map
        self.browser = QtWebEngineWidgets.QWebEngineView()
        self.layout.addWidget(self.browser)

        # Placeholder for telemetry data
        self.latitude = None
        self.longitude = None
        self.map_file = "live_gps_map.html"
        self.location_updated.connect(self.update_map)

        # Timer for periodic updates (drives update_gui)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(1000)

        # Create and load the initial persistent map page
        self.create_initial_map()

    @pyqtSlot(float, float)
    def update_map(self, latitude: float, longitude: float):
        try:
            self.latitude = latitude
            self.longitude = longitude

            # Run JS on the loaded page to update the marker in-place.
            page = self.browser.page()
            if page is not None:
                js = f"(function(){{ if (typeof updateMarker === 'function') updateMarker({latitude}, {longitude}); }})();"
                page.runJavaScript(js)
        except Exception as e:
            print(f"Error updating map via JS: {e}")

    def update_gui(self):
        try:
            if self.latitude is not None and self.longitude is not None:
                # Call the JS update function (no full reload)
                self.update_map(self.latitude, self.longitude)
        except Exception as e:
            print(f"Error updating GUI: {e}")

    def create_initial_map(self):
        try:
            # Default startup coords (can be changed later via location_updated)
            initial_latitude = 34.7295
            initial_longitude = -86.5853

            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"/>
            <style>html, body, #map {{ height:100%; margin:0; padding:0; }}</style>
            </head>
            <body>
            <div id="map"></div>
            <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
            <script>
                var map = L.map('map').setView([{initial_latitude}, {initial_longitude}], 17);
                L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }}).addTo(map);

                // Create a single marker that we'll move later
                var marker = L.marker([{initial_latitude}, {initial_longitude}]).addTo(map);

                // Exposed function for Python to call via runJavaScript
                function updateMarker(lat, lon) {{
                try {{
                    marker.setLatLng([lat, lon]);
                    map.setView([lat, lon]);
                }} catch (e) {{
                    console.error('updateMarker error:', e);
                }}
                }}
            </script>
            </body>
            </html>
            """

            # Save and load the HTML file once
            with open(self.map_file, 'w', encoding='utf-8') as f:
                f.write(html)

            # Load the local file into the web view
            self.browser.setUrl(QtCore.QUrl.fromLocalFile(os.path.abspath(self.map_file)))
        except Exception as e:
            print(f"Error creating initial map: {e}")

    def start(self):
        """Show the map window and run the Qt event loop."""
        self.win.show()
        sys.exit(self.app.exec_())