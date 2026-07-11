congress-legislators (Civiq fork)
=================================

Members of the United States Congress (1789–Present), congressional committees (1973–Present), committee membership (current only), and presidents and vice presidents of the United States in YAML format.

This is Civiq's fork of [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators), used as a submodule of `civiq-backend-svr`. The YAML files in this repository are the source of truth; the scripts in `scripts/` refresh them from official sources.

The full upstream README — including the complete field-by-field documentation of every YAML file — is preserved in [Readme_old.md](Readme_old.md). This file documents what is actually here and usable as of July 2026 (scripts verified on Python 3.14).

Data files
----------

File | Description
---- | -----------
`legislators-current.yaml` | Currently serving Members of Congress.
`legislators-historical.yaml` | Historical Members of Congress (everyone not in the current file).
`legislators-social-media.yaml` | Current official social media accounts for Members of Congress.
`committees-current.yaml` | Current committees of the Congress, with subcommittees.
`committee-membership-current.yaml` | Current committee/subcommittee assignments.
`committees-historical.yaml` | Current and historical committees from the 93rd Congress (1973) on.
`legislators-district-offices.yaml` | District offices for current Members of Congress.
`executive.yaml` | Presidents and vice presidents.

See [Readme_old.md](Readme_old.md) for the schema of each file.

Setup
-----

```bash
cd scripts
python3 -m venv virt
source virt/bin/activate
pip install -r requirements.txt
```

All scripts are run from the `scripts/` directory and edit the YAML files in the repository root in place. Check what changed afterwards with:

```bash
git diff ../*.yaml
```

Downloaded source data is cached under `scripts/cache/` (gitignored).

Working scripts
---------------

### Regular data updaters

Script | What it does | Usage
------ | ------------ | -----
`house_contacts.py` | Updates House members' address, office, phone, and `official_full` name from the Clerk's XML feed. | `python house_contacts.py`
`senate_contacts.py` | Updates senator party, class, state_rank, address, office, phone, contact_form, bioguide and LIS IDs from senate.gov. | `python senate_contacts.py`
`house_websites.py` | Updates House members' current website URLs by scraping house.gov (one request per member; takes a few minutes). | `python house_websites.py`
`committee_membership.py` | Rebuilds `committee-membership-current.yaml` and updates `committees-current.yaml` from the House Clerk and senate.gov. | `python committee_membership.py`
`contact_forms.py` | Sets each current member's `contact_form` URL from [unitedstates/contact-congress](https://github.com/unitedstates/contact-congress). Optionally pass bioguide IDs to limit the run. | `python contact_forms.py` or `python contact_forms.py A000055 B001230`
`historical_committees.py` | Updates `committees-historical.yaml` from govinfo BILLSTATUS bulk data. The `--cache` flag is required; the bulk zips are large, so limit to one congress when you can. | `python historical_committees.py --cache --congress=119`
`icpsr_ids.py` | Updates ICPSR IDs from Voteview roll-call data. `--congress` is required. | `python icpsr_ids.py --congress=119` (optionally `--bioguide=A000055`)
`pictorial_ids.py` | Updates GPO Pictorial Directory IDs. `--congress` is required (110 or later). | `python pictorial_ids.py --congress=119` (optionally `--bioguide=...`, `--refresh`)
`wikidata_update.py` | Fills in Wikidata IDs and cross-references (OpenSecrets, VoteSmart, Ballotpedia, C-SPAN, Google KG) via the Wikidata SPARQL endpoint. | `python wikidata_update.py`
`wikipedia_ids.py` | Updates `wikipedia` (and CongLinks-derived) IDs by scanning pages that embed the CongBio/CongLinks templates. Fetches thousands of pages at a throttled 60 requests/minute — a full fresh run takes hours. `--cache` reuses previously downloaded pages. | `python wikipedia_ids.py --cache`
`house_history.py` | Fills in `house_history` IDs by probing history.house.gov. With no arguments it scans IDs 22000–25000; pass explicit IDs to limit it. | `python house_history.py` or `python house_history.py 23001 23002`
`social_media.py` | Maintains `legislators-social-media.yaml`. `--sweep` scrapes member websites for account leads and writes a CSV for manual review; `--update` applies a reviewed CSV. Other modes: `--clean`, `--verify`, `--resolveyt`, `--resolvetw`, `--resolveig`. | `python social_media.py --service=twitter --sweep` then `python social_media.py --service=twitter --update`

### Maintenance and housekeeping

Script | What it does | Usage
------ | ------------ | -----
`lint.py` | Round-trips YAML files to normalize serialization. | `python lint.py` (all files) or `python lint.py ../legislators-current.yaml`
`office_validator.py` | Validates district office data; exits nonzero when there are findings (used by CI). | `python office_validator.py` (optionally `--skip-warnings`)
`export_csv.py` | Converts a legislators YAML file to CSV on stdout. | `python export_csv.py ../legislators-current.yaml > legislators-current.csv`
`alternate_bulk_formats.py` | Generates JSON for all YAML files and CSV for legislators and district offices into `alternate_formats/` (gitignored). | `python alternate_bulk_formats.py`
`sweep.py` | Removes out-of-office members from committee membership, social media, and district office files. | `python sweep.py`
`retire.py` | Ends a member's current term and moves them to the historical file. | `python retire.py A000055 2026-12-31`
`untire.py` | Moves a member back from historical to current and starts a new term (edit the term details afterwards). | `python untire.py A000055`
`election_results.py` | One-time transition to a new Congress from an election-results spreadsheet (`archive/election_results_{year}.csv`). Edit `ELECTION_YEAR` in the script first. **Do not run casually** — it retires members en masse. | `python election_results.py`

### Scripts that need external inputs

Script | Requirement | Usage
------ | ----------- | -----
`bioguide_xml.py` | A `BioguideProfiles.zip` bulk download from the [Biographical Directory](https://bioguide.congress.gov). This is the modern replacement for the retired `bioguide.py` scraper. | `python bioguide_xml.py path/to/BioguideProfiles.zip`
`geocode_offices.py` | A Google Maps API key in `scripts/cache/google_maps_api_key.txt`. Geocodes district offices that don't have coordinates yet. | `python geocode_offices.py` or `python geocode_offices.py A000055`

Obsolete scripts (data sources no longer exist)
-----------------------------------------------

These are kept for reference but cannot work anymore:

* `bioguide.py` — scraped `bioguide.congress.gov/scripts/biodisplay.pl`, which no longer exists. The current site is a JavaScript app behind Cloudflare bot protection; use `bioguide_xml.py` with the bulk data download instead. (The script exits 0 but updates nothing.)
* `bioguide_guess_new_member_ids.py` — probed the same retired endpoint for unassigned bioguide IDs; unknown IDs no longer 404, so its stop condition never fires and it loops forever.
* `thomas_ids.py` — scraped `beta.congress.gov`, which was decommissioned. THOMAS IDs are frozen legacy identifiers.
* `influence_ids.py` — used the Sunlight Foundation Influence Explorer API, which shut down with the organization.
* `cspan.py` — used the ProPublica Represent API, which has been retired.

`scripts/archive/` contains older one-off scripts from upstream and is not maintained.

Conventions
-----------

Every script in `scripts/` is import-safe: work happens in a `run()` function invoked under `if __name__ == '__main__':`. Shared helpers live in `scripts/utils.py` (`load_data`/`save_data` for the YAML files, `download` for cached HTTP fetches, `flags()`/`args()` for command-line parsing).

YAML loading is accelerated by `.pickle` sidecar caches next to each data file; they are hash-validated and rebuilt automatically, and are gitignored.

Public domain
-------------

This project is [dedicated to the public domain](LICENSE). As spelled out in [CONTRIBUTING](CONTRIBUTING.md):

> The project is in the public domain within the United States, and copyright and related rights in the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](http://creativecommons.org/publicdomain/zero/1.0/).
