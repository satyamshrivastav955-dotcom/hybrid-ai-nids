# data/

Place genuine CICIDS2017 CSVs in `data/raw/` (Monday-Friday flow files), then:

```
python scripts/prepare_data.py --raw data/raw --out data --protocol all
```

Splits land in `data/splits/` (`*_train/val/test.parquet` + `*_meta.json`);
manifest in `data/metadata/manifest.json`. Raw files are git-ignored; only the
manifest is committed. `--synthetic` generates watermarked DEMO data for smoke
tests only — never for research evaluation.
