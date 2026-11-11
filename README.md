# MOTO-HUB bike setups

Community catalogue of bike setups for
[MOTO-HUB ADV-SOLO](https://github.com/vincenzobpt/MOTO-HUB-ADV-SOLO-releases). A setup is the
configuration of one motorcycle: how the phone reaches the bike's screen, the video and Android
Auto options, screen margins, link options and, when the rider chooses, the dashboard.

The app reads `index.json` from this repository, so riders can browse the catalogue and install a
setup for their model without starting from scratch.

[![Discord](https://img.shields.io/badge/Discord-join%20the%20community-5865F2?logo=discord&logoColor=white)](https://discord.gg/FzhXZtPhC8)
[![Website](https://img.shields.io/badge/website-motohub.techub.eu-111111)](https://motohub.techub.eu)
[![Get MOTO-HUB ADV-SOLO](https://img.shields.io/badge/app-MOTO--HUB%20ADV--SOLO-e10600?logo=android&logoColor=white)](https://github.com/vincenzobpt/MOTO-HUB-ADV-SOLO-releases/releases/latest)

## Sharing a setup

1. In MOTO-HUB ADV-SOLO open **Garage ▸ your motorcycle ▸ Share setup ▸ Share with the community**.
2. The app packs the setup into one file. It reaches the MOTO-HUB support collector, where it is
   checked and, only when it looks right, added here.

## What a package contains

Each setup is a single `.mhp` file: a small manifest with the bike's name, brand and model, the
setup itself and, optionally, the rider's own dashboard. Packages never contain Wi-Fi names,
passwords or photos.

## Repository layout

- `setups/<brand>/<id>.mhp`: one package per setup, at most 2 MB.
- `index.json`: the list of all setups. It is generated, never edited by hand.
- `verified.json`: the maintainers' JSON array of verified setup ids; `verified` in `index.json` comes only from this file, never from a package's manifest.
- `tools/build_index.py`: checks every package and rebuilds `index.json`. Every pull request runs
  it with `--check`.

## License

Released under CC0 1.0. See `LICENSE`.

## Community

Questions, or a setup that does not behave as expected: tell us on the
**[MOTO-HUB Discord](https://discord.gg/FzhXZtPhC8)** and quote the Support ID from
**Settings ▸ 8 Diagnostics**. News and release notes are on
**[motohub.techub.eu](https://motohub.techub.eu)**.
