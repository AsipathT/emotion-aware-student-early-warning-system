# Data

Datasets are not stored in git. Download each one and place it in data/raw/.

| Dataset | Folder | Source |
|---|---|---|
| GoEmotions | data/raw/goemotions/ | Google Research, 28-emotion Reddit dataset |
| Emotion dataset (eng_dataset.csv, 4 classes) | data/raw/emotion4/ | Team shared drive (mostly tweets, not original ISEAR) |
| Domain set (self-built) | data/processed/ | Built by this component |

interim/ holds cleaned or mapped data. processed/ holds train, validation and test splits.
Never commit student messages. Scrub text with scrub_text() before use.

After cloning, create the folders data/raw, data/interim and data/processed (git does not track empty folders).
