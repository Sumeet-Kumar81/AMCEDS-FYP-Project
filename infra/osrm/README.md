Owner: Khalid (download Day 1, container Day 3).
1. Download Pakistan/Sindh .osm.pbf from Geofabrik into this folder (git-ignored).
2. osrm-extract -p /opt/car.lua x.osm.pbf ; osrm-partition ; osrm-customize
3. osrm-routed --algorithm mld x.osrm  (port 5000)
Test: GET http://localhost:5000/route/v1/driving/68.85,27.70;68.87,27.72
