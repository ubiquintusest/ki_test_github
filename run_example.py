from dwd_weather import get_air_temperature_by_postal_code


def main() -> None:
    result = get_air_temperature_by_postal_code(
        "10115", "2024-01-01", "2024-01-07"
    )
    print(result)


if __name__ == "__main__":
    main()
