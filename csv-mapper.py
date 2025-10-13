#!/usr/bin/env python3
import argparse, csv, json, os, re, sys
from typing import Any, Dict, List, Union

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # Only needed if the mapping file is YAML

KEY_PATTERN = re.compile(r"^key\((.*)\)$", re.IGNORECASE)

MappingValue = Union[str, List[str], Dict[str, Any]]
MappingDict = Dict[str, MappingValue]

def load_mapping(path: str) -> MappingDict:
    _, ext = os.path.splitext(path.lower())
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if ext in [".yaml", ".yml"]:
        if yaml is None:
            sys.exit("Mapping file is YAML, but PyYAML isn't available. "
                     "Install dependencies with `uv sync` first.")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        sys.exit("Mapping root must be an object/dict.")
    return data  # type: ignore[return-value]

def value_from_row(row: Dict[str, str], spec: MappingValue) -> str:
    """
    Evaluate mapping spec against a CSV row.

    Allowed forms:
      - "source_col"                      -> value from that column
      - ["col1","col2",...]               -> joined with a space
      - {"concat": [...], "sep": " "}     -> advanced concat with custom sep
      - "key(Some Constant)"              -> constant string
      - {"key": "Some Constant"}          -> constant string (alt form)
    """
    # Dict form (concat or key)
    if isinstance(spec, dict):
        if "key" in spec:
            return str(spec["key"])
        if "concat" in spec:
            cols = spec.get("concat", [])
            if not isinstance(cols, list):
                raise ValueError("`concat` must be a list of column names.")
            sep = str(spec.get("sep", " "))
            parts = [row.get(c, "") for c in cols]
            return sep.join([p.strip() for p in parts if p is not None])
        raise ValueError(f"Unknown mapping object keys: {list(spec.keys())}")

    # List form: join with a space
    if isinstance(spec, list):
        parts = [row.get(c, "") for c in spec]
        return " ".join([p.strip() for p in parts if p is not None])

    # String form
    if isinstance(spec, str):
        m = KEY_PATTERN.match(spec.strip())
        if m:
            return m.group(1)
        # otherwise treat as source column name
        return row.get(spec, "")

    raise ValueError(f"Unsupported mapping spec type: {type(spec)}")

def infer_input_fieldnames(sample_path: str, delimiter: str) -> List[str]:
    with open(sample_path, "r", encoding="utf-8-sig", newline="") as f:
        sniffer = csv.Sniffer()
        has_header = sniffer.has_header(f.read(4096))
        f.seek(0)
        reader = csv.DictReader(f, delimiter=delimiter)
        if not has_header or reader.fieldnames is None:
            sys.exit("Input CSV appears to be missing a header row.")
        # Strip whitespace from column names
        return [field.strip() for field in reader.fieldnames]

def transform_csv(
    in_path: str,
    out_path: str,
    mapping: MappingDict,
    delimiter_in: str = ",",
    delimiter_out: str = ",",
    strict: bool = False,
) -> None:
    # Validate mapping keys are strings
    for k in mapping.keys():
        if not isinstance(k, str):
            sys.exit("All top-level mapping keys (output column names) must be strings.")

    # Determine input headers
    input_headers = infer_input_fieldnames(in_path, delimiter_in)

    # Warn for missing referenced columns (best-effort precheck)
    referenced_cols = set()
    def collect(spec: MappingValue):
        if isinstance(spec, str):
            if not KEY_PATTERN.match(spec):
                referenced_cols.add(spec)
        elif isinstance(spec, list):
            for c in spec:
                referenced_cols.add(c)
        elif isinstance(spec, dict):
            if "concat" in spec and isinstance(spec["concat"], list):
                for c in spec["concat"]:
                    referenced_cols.add(c)

    for v in mapping.values():
        collect(v)

    missing = sorted(c for c in referenced_cols if c not in input_headers)
    if missing:
        msg = f"Warning: input is missing referenced columns: {missing}."
        if strict:
            sys.exit("Strict mode: " + msg)
        else:
            print(msg, file=sys.stderr)

    with open(in_path, "r", encoding="utf-8-sig", newline="") as fin, \
         open(out_path, "w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fin, delimiter=delimiter_in)
        out_headers = list(mapping.keys())
        writer = csv.DictWriter(fout, fieldnames=out_headers, delimiter=delimiter_out)
        writer.writeheader()

        for row in reader:
            # Strip whitespace from column names in the row
            row = {k.strip(): v for k, v in row.items()}
            out_row = {}
            for out_col, spec in mapping.items():
                try:
                    out_row[out_col] = value_from_row(row, spec)
                except Exception as e:
                    if strict:
                        raise
                    print(f"Warning: failed to compute column '{out_col}': {e}", file=sys.stderr)
                    out_row[out_col] = ""
            writer.writerow(out_row)

def main():
    p = argparse.ArgumentParser(
        description="Map/transform CSV columns, concatenate fields, and add constant columns."
    )
    p.add_argument("--in", dest="in_path", required=True, help="Input CSV path")
    p.add_argument("--out", dest="out_path", required=True, help="Output CSV path")
    p.add_argument("--map", dest="map_path", required=True, help="Mapping file (.json/.yaml)")
    p.add_argument("--sep-in", dest="sep_in", default=",", help="Input CSV delimiter (default ,)")
    p.add_argument("--sep-out", dest="sep_out", default=",", help="Output CSV delimiter (default ,)")
    p.add_argument("--strict", action="store_true", help="Fail on missing columns or errors")
    args = p.parse_args()

    mapping = load_mapping(args.map_path)
    transform_csv(
        in_path=args.in_path,
        out_path=args.out_path,
        mapping=mapping,
        delimiter_in=args.sep_in,
        delimiter_out=args.sep_out,
        strict=args.strict,
    )
if __name__ == "__main__":
    main()

