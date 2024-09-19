import argparse
import json
import matplotlib.pyplot as plt


def plot_aggregated_discontinuities_from_benchmark(json_path, plot_path):
    """
    Aggregates and visualizes the distribution of discontinuities for chunk and frame data
    from a benchmark JSON file.

    The function reads discontinuity data from a JSON file (produced by the benchmark function),
    accumulates the count, gaps, and differences for each type of discontinuity (Type I, II, III, IV)
    for both chunk_serial and frame_ids, and generates plots.

    Args:
        json_path (str): Path to the input JSON file containing discontinuity data.
        plot_path (str): Path to save the generated plot as an image.
    """
    aggregate_results = {
        "chunk": {
            "type_i": {"count": [], "gaps": []},
            "type_ii": {"count": [], "gaps": []},
            "type_iii": {"count": [], "gaps": [], "differences": {}},
            "type_iv": {"count": [], "gaps": []},
        },
        "frame": {
            "type_i": {"count": [], "gaps": []},
            "type_ii": {"count": [], "gaps": []},
            "type_iii": {"count": [], "gaps": [], "differences": {}},
            "type_iv": {"count": [], "gaps": []},
        },
    }

    with open(json_path, "r") as f:
        data = json.load(f)

    # Aggregate discontinuity data for both chunk_serial and frame_ids
    for nev_file, nev_data in data.items():
        for dataset in ["chunk", "frame"]:
            discontinuities = nev_data[f"{dataset}_discontinuities"]
            for discontinuity_type in aggregate_results[dataset].keys():
                count = discontinuities[discontinuity_type]["count"]
                if count > 0:
                    aggregate_results[dataset][discontinuity_type]["count"].append(
                        count
                    )

                aggregate_results[dataset][discontinuity_type]["gaps"].extend(
                    discontinuities[discontinuity_type]["gaps"]
                )

                if discontinuity_type == "type_iii":
                    for diff, freq in discontinuities["type_iii"][
                        "differences"
                    ].items():
                        if (
                            diff
                            in aggregate_results[dataset]["type_iii"]["differences"]
                        ):
                            aggregate_results[dataset]["type_iii"]["differences"][
                                diff
                            ] += freq
                        else:
                            aggregate_results[dataset]["type_iii"]["differences"][
                                diff
                            ] = freq

    fig, axes = plt.subplots(8, 3, figsize=(20, 40))
    fig.suptitle(
        f"Aggregated Discontinuity Distributions (Chunk and Frame)", fontsize=16
    )

    datasets = [
        ("Chunk", aggregate_results["chunk"]),
        ("Frame", aggregate_results["frame"]),
    ]

    discontinuity_types = [
        ("Type I", "type_i"),
        ("Type II", "type_ii"),
        ("Type III", "type_iii"),
        ("Type IV", "type_iv"),
    ]

    for d, (dataset_name, dataset_results) in enumerate(datasets):
        for i, (name, discontinuity_type) in enumerate(discontinuity_types):
            discontinuity = dataset_results[discontinuity_type]
            counts = discontinuity["count"]
            gaps = discontinuity["gaps"]

            # Plot Counts Distribution
            if counts:
                axes[d * 4 + i, 0].hist(
                    counts, bins=30, color="blue", edgecolor="black"
                )
                axes[d * 4 + i, 0].set_title(
                    f"{dataset_name} {name} Counts Distribution"
                )
                axes[d * 4 + i, 0].set_ylabel("Frequency")
            else:
                axes[d * 4 + i, 0].text(
                    0.5, 0.5, "No Counts", ha="center", va="center", fontsize=12
                )
                axes[d * 4 + i, 0].set_title(
                    f"{dataset_name} {name} Counts Distribution"
                )

            # Plot Gaps Distribution
            if gaps:
                axes[d * 4 + i, 1].hist(
                    gaps, bins=30, color="orange", edgecolor="black"
                )
                axes[d * 4 + i, 1].set_title(f"{dataset_name} {name} Gaps Distribution")
                axes[d * 4 + i, 1].set_ylabel("Frequency")
            else:
                axes[d * 4 + i, 1].text(
                    0.5, 0.5, "No Gaps", ha="center", va="center", fontsize=12
                )
                axes[d * 4 + i, 1].set_title(f"{dataset_name} {name} Gaps Distribution")

            # Plot Type III Differences (only for Type III)
            if discontinuity_type == "type_iii":
                differences = discontinuity["differences"]
                if differences:
                    diffs = list(differences.keys())
                    freqs = list(differences.values())
                    axes[d * 4 + i, 2].bar(
                        diffs, freqs, color="green", edgecolor="black"
                    )
                    axes[d * 4 + i, 2].set_title(
                        f"{dataset_name} Type III Differences Distribution"
                    )
                    axes[d * 4 + i, 2].set_ylabel("Frequency")
                else:
                    axes[d * 4 + i, 2].text(
                        0.5,
                        0.5,
                        "No Differences",
                        ha="center",
                        va="center",
                        fontsize=12,
                    )
                    axes[d * 4 + i, 2].set_title(
                        f"{dataset_name} Type III Differences Distribution"
                    )
            else:
                axes[d * 4 + i, 2].axis("off")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(plot_path)
    plt.close()


def main():
    """
    Main function to handle command-line interface for generating aggregated discontinuity plots from benchmark JSON.
    Parses the input and output paths and calls the plot function.
    """
    parser = argparse.ArgumentParser(
        description="Plot aggregated discontinuities from a benchmark JSON file."
    )
    parser.add_argument(
        "json_path", type=str, help="Path to the input benchmark JSON file."
    )
    parser.add_argument("plot_path", type=str, help="Path to save the output plot.")

    args = parser.parse_args()

    plot_aggregated_discontinuities_from_benchmark(args.json_path, args.plot_path)


if __name__ == "__main__":
    main()
