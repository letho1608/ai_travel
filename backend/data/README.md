# Runtime data

Generated data lives here and carries provider/fetched-at/license metadata.

```powershell
python scripts/import_osm_places.py --output data/places.json
python scripts/build_osrm_matrix.py --places data/places.json --output data/distance_matrix.json
```

The public OSRM endpoint is suitable only for PoC/small imports. Production must run the validated Hanoi profile offline and upload the generated matrix. Never relabel the public `driving` profile as motorcycle routing.

