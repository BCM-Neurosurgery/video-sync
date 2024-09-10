from pyvideosync.nev import Nev
import argparse


def main():
    parser = argparse.ArgumentParser(description="Plot camera exposure from NEV data.")

    parser.add_argument("--nev", required=True, help="Path to the NEV file")
    parser.add_argument("--plot_out_path", required=True, help="Path to save the plot")
    parser.add_argument("--start", type=int, default=0, help="Start time (default: 0)")
    parser.add_argument("--end", type=int, default=200, help="End time (default: 200)")

    args = parser.parse_args()

    nev_path = args.nev
    plot_save_path = args.plot_out_path
    start = args.start
    end = args.end

    nev = Nev(nev_path)

    nev.plot_cam_exposure_all(plot_save_path, start, end)


if __name__ == "__main__":
    main()
