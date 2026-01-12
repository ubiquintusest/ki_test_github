import argparse

from dwd_weather import get_air_temperature_by_postal_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch DWD air temperatures for a postal code."
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable SSL verification (use only for local debugging).",
    )
    args = parser.parse_args()
    result = get_air_temperature_by_postal_code(
        "10115",
        "2024-01-01",
        "2024-01-07",
        verify_ssl=not args.insecure,
    )
    print(result)


if __name__ == "__main__":
    main()
