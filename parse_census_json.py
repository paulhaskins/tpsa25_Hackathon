import pandas as pd
from pyjstat import pyjstat

def load_census_json(path: str) -> pd.DataFrame:
    """
    Load a CSO JSON-stat 2.0 census file and return a tidy DataFrame.
    
    Args:
        path (str): Path to JSON-stat file.

    Returns:
        pd.DataFrame: Flattened census data (dimensions as columns).
    """
    dataset = pyjstat.Dataset.read(path)
    df = dataset.write('dataframe')
    return df


if __name__ == "__main__":
    # Example: Ireland population by Small Area
    df = load_census_json("data/raw/census/population_small_area_2022.json")
    
    print(df.head(10))
    print("Columns:", df.columns.tolist())

    # Example output columns (will depend on dataset):
    # ['CensusYear', 'County', 'Small Area', 'Sex', 'Population']
    
    # Filter down to total population by area
    if "Sex" in df.columns:
        df = df[df["Sex"] == "Both sexes"]
    if "Statistic" in df.columns:
        df = df[df["Statistic"].str.contains("Population", case=False)]

    # Group by Small Area / Electoral Division
    grouped = df.groupby("Small Area")["value"].sum().reset_index()
    grouped = grouped.rename(columns={"value": "population"})

    print(grouped.head())
    # Save cleaned CSV
    grouped.to_csv("data/processed/population_by_small_area.csv", index=False)
