import pandas as pd
from pyvideosync.utils import (
    count_discontinuities,
    count_unique_values,
)


class DataFrameLogger:
    # df names: columns to check
    config = {
        "camera_json_df": ["frame_ids_reconstructed", "chunk_serial_data"],
        "nev_chunk_serial_df": ["chunk_serial"],
        "chunk_serial_df_joined": ["chunk_serial", "frame_ids_reconstructed"],
        "all_merged_df": ["chunk_serial", "frame_ids_reconstructed"],
    }

    def get_columns_to_check(self, df_name):
        """
        Get the columns to check for a specific dataframe.
        Parameters
            df_name (str): Name of the dataframe to get columns for.
        Returns
            List of columns to check.
        """
        return self.config.get(df_name, [])

    def log_dataframe_info(self, df_name, df):
        """
        Log information about the dataframe.
        Parameters
            df_name (str): Name of the dataframe.
            df (pd.DataFrame): Dataframe to log information for.
        Returns
            Dataframe containing the results.
        """
        results = {"column": [], "num_discontinuities": [], "num_unique_values": []}
        columns_to_check = self.get_columns_to_check(df_name)

        if columns_to_check:
            for column in columns_to_check:
                if column in df.columns:
                    num_discontinuities = count_discontinuities(df, column)
                    num_unique_values = count_unique_values(df, column)
                    results["column"].append(column)
                    results["num_discontinuities"].append(num_discontinuities)
                    results["num_unique_values"].append(num_unique_values)
                else:
                    print(f"{column} not found in columns")

        result_df = pd.DataFrame(results).set_index("column")
        return result_df
