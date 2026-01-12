import argparse
import ssl
import sys
import urllib.error

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
    try:
        result = get_air_temperature_by_postal_code(
            "10115",
            "2024-01-01",
            "2024-01-07",
            verify_ssl=not args.insecure,
        )
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            print(
                "SSL certificate verification failed. "
                "Rerun with --insecure to disable verification for local debugging.",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        raise
    print(result)


if __name__ == "__main__":
    main()
