import argparse
import json
import matplotlib.pyplot as plt


def plot_aggregated_discontinuities(json_path, plot_path):
    """
    Aggregates and visualizes the distribution of discontinuities across multiple NEV files.

    The function reads discontinuity data from a JSON file, accumulates the count, gaps, and differences for each type
    of discontinuity (Type I, II, III, IV), and generates plots showing the distribution of counts, gaps, and differences.
    For Type III, an additional plot for differences is included.

    Args:
        json_path (str): Path to the input JSON file containing discontinuity data.
        plot_path (str): Path to save the generated plot as an image.
    """
    aggregate_results = {
        "type_i": {"count": [], "gaps": []},
        "type_ii": {"count": [], "gaps": []},
        "type_iii": {"count": [], "gaps": [], "differences": {}},
        "type_iv": {"count": [], "gaps": []},
    }

    with open(json_path, "r") as f:
        data = json.load(f)

    for nev_file, nev_data in data.items():
        for discontinuity_type in aggregate_results.keys():
            count = nev_data[discontinuity_type]["count"]
            if count > 0:
                aggregate_results[discontinuity_type]["count"].append(count)

            aggregate_results[discontinuity_type]["gaps"].extend(
                nev_data[discontinuity_type]["gaps"]
            )

            if discontinuity_type == "type_iii":
                for diff, freq in nev_data["type_iii"]["differences"].items():
                    if diff in aggregate_results["type_iii"]["differences"]:
                        aggregate_results["type_iii"]["differences"][diff] += freq
                    else:
                        aggregate_results["type_iii"]["differences"][diff] = freq

    fig, axes = plt.subplots(4, 3, figsize=(20, 20))
    fig.suptitle(f"Aggregated Discontinuity Distributions", fontsize=16)

    discontinuity_types = [
        ("Type I", aggregate_results["type_i"]),
        ("Type II", aggregate_results["type_ii"]),
        ("Type III", aggregate_results["type_iii"]),
        ("Type IV", aggregate_results["type_iv"]),
    ]

    for i, (name, discontinuity) in enumerate(discontinuity_types):
        counts = discontinuity["count"]
        gaps = discontinuity["gaps"]

        if name != "Type III":
            if counts:
                axes[i, 0].hist(counts, bins=30, color="blue", edgecolor="black")
                axes[i, 0].set_title(f"{name} Counts Distribution")
                axes[i, 0].set_ylabel("Frequency")
            else:
                axes[i, 0].text(
                    0.5, 0.5, "No Counts", ha="center", va="center", fontsize=12
                )
                axes[i, 0].set_title(f"{name} Counts Distribution")

            if gaps:
                axes[i, 1].hist(gaps, bins=30, color="orange", edgecolor="black")
                axes[i, 1].set_title(f"{name} Gaps Distribution")
                axes[i, 1].set_ylabel("Frequency")
            else:
                axes[i, 1].text(
                    0.5, 0.5, "No Gaps", ha="center", va="center", fontsize=12
                )
                axes[i, 1].set_title(f"{name} Gaps Distribution")

            axes[i, 2].axis("off")

        else:
            if counts:
                axes[i, 0].hist(counts, bins=30, color="skyblue", edgecolor="black")
                axes[i, 0].set_title(f"{name} Counts Distribution")
                axes[i, 0].set_ylabel("Frequency")
            else:
                axes[i, 0].text(
                    0.5, 0.5, "No Counts", ha="center", va="center", fontsize=12
                )
                axes[i, 0].set_title(f"{name} Counts Distribution")

            if gaps:
                axes[i, 1].hist(gaps, bins=30, color="orange", edgecolor="black")
                axes[i, 1].set_title(f"{name} Gaps Distribution")
                axes[i, 1].set_ylabel("Frequency")
            else:
                axes[i, 1].text(
                    0.5, 0.5, "No Gaps", ha="center", va="center", fontsize=12
                )
                axes[i, 1].set_title(f"{name} Gaps Distribution")

            differences = discontinuity["differences"]
            if differences:
                diffs = list(differences.keys())
                freqs = list(differences.values())
                axes[i, 2].bar(diffs, freqs, color="green", edgecolor="black")
                axes[i, 2].set_title("Type III Differences Distribution")
                axes[i, 2].set_ylabel("Frequency")
            else:
                axes[i, 2].text(
                    0.5, 0.5, "No Differences", ha="center", va="center", fontsize=12
                )
                axes[i, 2].set_title("Type III Differences Distribution")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(plot_path)
    plt.close()


def main():
    """
    Main function to handle command-line interface for generating aggregated discontinuity plots.
    Parses the input and output paths and calls the plot function.
    """
    parser = argparse.ArgumentParser(
        description="Plot aggregated discontinuities from a JSON file."
    )
    parser.add_argument("json_path", type=str, help="Path to the input JSON file.")
    parser.add_argument("plot_path", type=str, help="Path to save the output plot.")

    args = parser.parse_args()

    plot_aggregated_discontinuities(args.json_path, args.plot_path)


if __name__ == "__main__":
    main()
