from abc import ABC, abstractmethod
import pandas as pd
import logging
from pyvideosync.utils import (
    count_discontinuities,
    count_unique_values,
)


class DataFrameBase(ABC):
    def __init__(self, df, logger) -> None:
        self.df = df
        self.logger = logger

    @abstractmethod
    def get_name(self) -> str:
        """
        Get the name of the DataFrame.

        Returns:
            str: The name of the DataFrame.
        """
        pass

    @abstractmethod
    def get_columns_to_check(self):
        """
        Get the columns to check for a specific dataframe.

        Returns
            List of columns to check.
        """
        pass

    def get_df(self):
        return self.df

    def log_dataframe(self):
        """
        Just print the dataframe in DEBUG level
        """
        self.logger.debug(f"{self.get_name}:\n{self.df}")

    def log_dataframe_info(self):
        """
        Log information about the dataframe in INFO level

        Returns
            Dataframe containing the results.
        """
        self.log_dataframe()
        results = {"column": [], "num_discontinuities": [], "num_unique_values": []}
        columns_to_check = self.get_columns_to_check()

        if columns_to_check:
            for column in columns_to_check:
                if column in self.df.columns:
                    num_discontinuities = count_discontinuities(self.df, column)
                    num_unique_values = count_unique_values(self.df, column)
                    results["column"].append(column)
                    results["num_discontinuities"].append(num_discontinuities)
                    results["num_unique_values"].append(num_unique_values)
                else:
                    self.logger.info(f"{column} not found in columns")

        result_df = pd.DataFrame(results).set_index("column")
        self.logger.info(f"{self.get_name()} stats:\n{result_df}")
        return result_df
