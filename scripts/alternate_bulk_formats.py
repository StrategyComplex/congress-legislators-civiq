"""Generate congressional bulk formats, with an isolated JSON-only build mode."""

import argparse
import csv
import json
import sys
from io import StringIO
from datetime import date, datetime
from pathlib import Path

if __name__ == '__main__':
    sys.dont_write_bytecode = True

from converter_safety import check_output_tree, check_path, load_yaml, output_file

ROOT = Path(__file__).resolve().parent.parent


def load_source_yaml(path):
    """Load safe YAML directly, ignoring and never creating pickle caches."""
    return load_yaml(path)


def format_date(value):
    """Preserve YAML calendar dates/timestamps as ISO strings in JSON."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError('Unsupported JSON value: ' + type(value).__name__)


def generate_legislator_csv(input_dir=ROOT, output_dir=ROOT / 'alternate_formats' / 'csv'):
    """Generate legacy legislator CSVs from source YAML, without pickle caches."""

    #yaml filenames
    yamls = ["legislators-current.yaml","legislators-historical.yaml"]
    yaml_social = "legislators-social-media.yaml"



    #list of yaml field name, csv column name tuples. Split into categories which do not reflect yaml structure (structured for logical csv column ordering)
    bio_fields = [
    ("last", "last_name"),
    ("first", "first_name"),
    ("middle", "middle_name"),
    ("suffix", "suffix"),
    ("nickname", "nickname"),
    ("official_full", "full_name"),
    ("birthday", "birthday"),
    ("gender", "gender")
    ]

    #ID crosswalks, omit FEC id's, which may contain (arbitrary?) number of values
    crosswalk_fields = [
    ("bioguide", "bioguide_id"),
    ("thomas", "thomas_id"),
    ("opensecrets", "opensecrets_id"),
    ("lis","lis_id"),
    ("fec","fec_ids"),
    ("cspan", "cspan_id"),
    ("govtrack", "govtrack_id"),
    ("votesmart", "votesmart_id"),
    ("ballotpedia", "ballotpedia_id"),
    ("washington_post", "washington_post_id"),
    ("icpsr", "icpsr_id"),
    ("wikipedia", "wikipedia_id")
    ]

    #separate list for children of "terms", csv only captures data for most recent term
    #currently excluding start/end dates - earliest start to latest end is deceptive (excludes gaps) as is start/end for most recent term
    term_fields = [
    ("type", "type"),
    ("state", "state"),
    ("district", "district"),
    ("class", "senate_class"),
    ("party", "party"),
    ("url", "url"),
    ("address", "address"),
    ("phone", "phone"),
    ("contact_form", "contact_form"),
    ("rss_url", "rss_url"),
    ]

    #pulled from legislators-social-media.yaml
    social_media_fields = [
    ("twitter", "twitter"),
    ("twitter_id", "twitter_id"),
    ("facebook", "facebook"),
    ("youtube", "youtube"),
    ("youtube_id", "youtube_id"),
    ("mastodon", "mastodon")
    ]


    print("Loading %s..." %yaml_social)
    social = load_source_yaml(Path(input_dir) / yaml_social)

    for filename in yamls:
        print("Converting %s to CSV..." % filename)

        legislators = load_source_yaml(Path(input_dir) / filename)

        #convert yaml to csv
        buffer = StringIO(newline='')
        csv_output = csv.writer(buffer)

        head = []
        for pair in bio_fields:
            head.append(pair[1])
        for pair in term_fields:
            head.append(pair[1])
        for pair in social_media_fields:
            head.append(pair[1])
        for pair in crosswalk_fields:
            head.append(pair[1])
        csv_output.writerow(head)

        for legislator in legislators:
            legislator_row = []
            for pair in bio_fields:
                if 'name' in legislator and pair[0] in legislator['name']:
                    legislator_row.append(legislator['name'][pair[0]])
                elif 'bio' in legislator and pair[0] in legislator['bio']:
                    legislator_row.append(legislator['bio'][pair[0]])
                else:
                    legislator_row.append(None)

            for pair in term_fields:
                latest_term = legislator['terms'][len(legislator['terms'])-1]
                if pair[0] in latest_term:
                    legislator_row.append(latest_term[pair[0]])
                else:
                    legislator_row.append(None)

            social_match = None
            for social_legislator in social:
                if 'bioguide' in legislator['id'] and 'bioguide' in social_legislator['id'] and legislator['id']['bioguide'] == social_legislator['id']['bioguide']:
                    social_match = social_legislator
                    break
                elif 'thomas' in legislator['id'] and 'thomas' in social_legislator['id'] and legislator['id']['thomas'] == social_legislator['id']['thomas']:
                    social_match = social_legislator
                    break
                elif 'govtrack' in legislator['id'] and 'govtrack' in social_legislator['id'] and legislator['id']['govtrack'] == social_legislator['id']['govtrack']:
                    social_match = social_legislator
                    break
            for pair in social_media_fields:
                if social_match != None:
                    if pair[0] in social_match['social']:
                        legislator_row.append(social_match['social'][pair[0]])
                    else:
                        legislator_row.append(None)
                else:
                    legislator_row.append(None)

            for pair in crosswalk_fields:
                if pair[0] in legislator['id']:
                    value = legislator['id'][pair[0]]
                    if isinstance(value, list):
                        # make FEC IDs comma-separated
                        value = ",".join(value)
                    legislator_row.append(value)
                else:
                    legislator_row.append(None)

            csv_output.writerow(legislator_row)

        with output_file(Path(output_dir) / filename.replace('.yaml', '.csv'), newline='') as output:
            output.write(buffer.getvalue())


def generate_district_office_csv(input_dir=ROOT, output_dir=ROOT / 'alternate_formats' / 'csv'):
    """Generate the legacy district-office CSV without source-side caches."""
    filename = "legislators-district-offices.yaml"
    print("Converting %s to CSV..." % filename)
    legislators_offices = load_source_yaml(Path(input_dir) / filename)
    fields = [
        "bioguide", "thomas", "govtrack", "id", "address", "building",
        "city", "fax", "hours", "phone", "state", "suite", "zip",
        "latitude", "longitude"]

    f = StringIO(newline='')
    csv_output = csv.DictWriter(f, fieldnames=fields)
    csv_output.writeheader()

    for legislator_offices in legislators_offices:
        legislator_ids = legislator_offices['id']
        for office in legislator_offices['offices']:
            office.update(legislator_ids)
            csv_output.writerow(office)

    with output_file(Path(output_dir) / filename.replace('.yaml', '.csv'), newline='') as output:
        output.write(f.getvalue())


def generate_legislator_json(input_dir=None, output_dir=None, *, force_refresh=True):
    """Convert sorted root *.yaml files into a JSON destination, without CSV.

    The API retains its historical refresh default. Explicit CLI destinations
    skip existing files unless --force-refresh is supplied. Publication and
    complete-dataset validation belong to the caller, not this converter.
    """
    input_dir = Path(input_dir) if input_dir is not None else ROOT
    output_dir = Path(output_dir) if output_dir is not None else ROOT / 'alternate_formats' / 'json'
    check_output_tree(output_dir)
    for source in sorted(input_dir.glob('*.yaml')):
        filename = source.name
        destination = output_dir / (source.stem + '.json')
        check_path(destination)
        if destination.exists() and not force_refresh:
            continue
        print("Converting %s to JSON..." % filename)
        data = load_source_yaml(source)
        '''handle edge case of incorrect coercion for twitter ids in social media data
            json/js can only handle maximum of 53-bit integers, so 64-bit integer twitter ids *must* be stringified
            to consistently preserve value in json. otherwise they may be rounded and malformed
        '''
        if 'legislators-social-media' in filename:
            for social_legislator in data:
                if 'twitter_id' in social_legislator['social']:
                    social_legislator['social']['twitter_id'] = str(social_legislator['social']['twitter_id'])

        #convert yaml to json
        with output_file(destination) as output:
            output.write(json.dumps(data, default=format_date, indent=2))


def generate_committee_membership_csv(input_dir=ROOT, output_dir=ROOT / 'alternate_formats' / 'csv'):
    """Generate the legacy membership CSV without mutating source files."""
    filename = "committee-membership-current.yaml"
    print("Converting %s to CSV..." % filename)
    committee_membership = load_source_yaml(Path(input_dir) / filename)
    fields = [
        "bioguide", "name",
        "committee_id", "committee_type", "committee_name", "committee_subcommittee_name",
        "party", "title", "rank", "chamber",
        ]

    committes = load_source_yaml(Path(input_dir) / "committees-current.yaml")
    committes = { committee["thomas_id"]: committee
                  for committee in committes }
    for committee in list(committes.values()):
        committee["id"] = committee["thomas_id"]
        for subcommittee in committee.get("subcommittees", []):
            subcommittee["id"] = committee["thomas_id"] + subcommittee["thomas_id"]
            subcommittee["type"] = committee["type"] + " subcommittee"
            subcommittee["subcommittee_name"] = subcommittee["name"]
            subcommittee["name"] = committee["name"]
            committes[subcommittee["id"]] = subcommittee
    committee_keys = ["id", "type", "name", "subcommittee_name"]

    f = StringIO(newline='')
    csv_output = csv.DictWriter(f, fieldnames=fields)
    csv_output.writeheader()

    for committee_id, members in committee_membership.items():
        for member in members:
            for key in committee_keys:
                member["committee_" + key] = committes[committee_id].get(key, "")
            csv_output.writerow(member)

    with output_file(Path(output_dir) / filename.replace('.yaml', '.csv'), newline='') as output:
        output.write(f.getvalue())


def main(argv=None):
    """Run from any working directory; an explicit build destination is JSON-only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=ROOT,
                        help='directory containing congressional *.yaml sources')
    parser.add_argument('--output-dir', type=Path,
                        help='JSON destination root; requires --json-only')
    parser.add_argument('--json-only', action='store_true',
                        help='do not read CSV-only inputs or generate CSV')
    parser.add_argument('--force-refresh', action='store_true',
                        help='overwrite existing files in an explicit destination')
    args = parser.parse_args(argv)
    if not args.input_dir.is_dir():
        parser.error('--input-dir must be an existing directory')
    if args.output_dir is not None:
        if not args.json_only:
            parser.error('--output-dir requires --json-only to isolate build output')
        if args.output_dir.resolve().is_relative_to(args.input_dir.resolve()):
            parser.error('--output-dir must be outside --input-dir')
    if not args.json_only:
        check_output_tree(ROOT / 'alternate_formats' / 'csv')
        check_output_tree(ROOT / 'alternate_formats' / 'json')
        generate_legislator_csv(args.input_dir)
        generate_district_office_csv(args.input_dir)
    generate_legislator_json(args.input_dir, args.output_dir,
                             force_refresh=args.force_refresh or args.output_dir is None)
    if not args.json_only:
        generate_committee_membership_csv(args.input_dir)


if __name__ == '__main__':
    main()
