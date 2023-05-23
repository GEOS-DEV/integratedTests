
import os
import argparse
import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
import hdf5_wrapper


unit_map = {'milliseconds': 1e-3,
            'seconds': 1.0,
            'minutes': 60.0,
            'hours': 60.0 * 60.0,
            'days': 60.0 * 60.0 * 24.0,
            'years': 60.0 * 60.0 * 24.0 * 365.25}


def interpolate_values_time(ta, xa, tb):
    """
    Interpolate array values in time

    Args:
        ta (np.ndarray): Target time array
        xa (np.ndarray): Target value array
        tb (np.ndarray): Baseline time array

    Returns:
        np.ndarray: Interpolated value array
    """
    N = list(np.shape(xa))
    M = len(tb)

    if (len(N) == 1):
        return interp1d(ta, xa)(tb)
    else:
        # Reshape the input array so that we can work on the non-time axes
        S = np.product(N[1:])
        xc = np.reshape(xa, (N[0], S))
        xd = np.zeros((len(tb), S))
        for ii in range(S):
            xd[:, ii] = interp1d(ta, xc[:, ii])(tb)

        # Return the array to it's expected shape
        N[0] = M
        return np.reshape(xd, N)


def check_diff(parameter_name, set_name, target, baseline, tolerance, errors):
    """
    Compute the L2-norm of the diff and compare to the set tolerance

    Args:
        parameter_name (str): Parameter name
        set_name (str): Set name
        target (np.ndarray): Target value array
        baseline (np.ndarray): Baseline value array
        tolerance (float): Required tolerance of diff
        errors (list): List to add any errors

    Returns:
        np.ndarray: Interpolated value array
    """
    dx = target - baseline
    diff = np.sqrt(np.sum(dx * dx)) / len(dx)
    if (diff > tolerance):
        errors.append(f'{parameter_name}_{set_name} diff exceeds tolerance: ||t-b||={diff}, tolerance={tolerance}')


def curve_check_figure(parameter_name, set_name, data, data_sizes, output_root, ncol, units_time):
    """
    Generate figures associated with the curve check

    Args:
        parameter_name (str): Parameter name
        set_name (str): Set name
        data (dict): Dictionary of curve data
        data_sizes (dict): Dictionary of curve data sizes
        output_root (str): Path of the folder to place the figures
        ncol (int): Number of columns to use in the figure
        units_time (str): Time units for the figure
    """
    # Setup
    style = {'target': {'marker': '', 'linestyle': '-'},
             'baseline': {'marker': '.', 'linestyle': ''}}
    time_key = f'{parameter_name} Time'
    value_key = f'{parameter_name} {set_name}'
    s = data_sizes[parameter_name][set_name]
    N = s[list(s.keys())[0]]
    nrow = int(np.ceil(float(N[2]) / ncol))
    time_scale = unit_map[units_time]
    time_label = f'Time ({units_time})'

    # Create the figure
    fig = plt.figure(figsize=(8, 6))
    for ii in range(N[2]):
        ax = plt.subplot(nrow, ncol, ii + 1)
        for k in s.keys():
            t = np.squeeze(data[k][time_key]) / time_scale
            x = np.squeeze(data[k][value_key][:, :, ii])

            if (N[1] == 1):
                ax.plot(t, x, label=k, **style[k])

            else:
                cmap = plt.get_cmap('jet')
                for jj in range(N[1]):
                    c = cmap(float(jj) / N[1])
                    kwargs = {}
                    if (jj == 0):
                        kwargs['label'] = k
                    ax.plot(t, x[:, jj], color=c, **style[k], **kwargs)

        # Set labels
        ax.set_xlabel(time_label)
        ax.set_ylabel(value_key)
        ax.set_xlim(t[[0, -1]])
        ax.legend(loc=2)
    plt.tight_layout()
    fig.savefig(os.path.join(output_root, f'{value_key}.png'), dpi=200)


def compare_time_history_curves(fname, baseline, curve, tolerance, output, output_n_column, units_time):
    """
    Compute time history curves

    Args:
        fname (str): Target curve file name
        baseline (str): Baseline curve file name
        curve (list): list containing pairs of value and set names to test
        tolerance (np.ndarray): Baseline value array
        output (str): Path to place output figures
        ncol (int): Number of columns to use in the figure
        units_time (str): Time units for the figure

    Returns:
        tuple: warnings, errors
    """
    # Setup
    files = {'target': fname, 'baseline': baseline}
    warnings = []
    errors = []

    # Load data and check sizes
    data = {}
    data_sizes = {}
    for k, f in files.items():
        if os.path.isfile(f):
            data[k] = hdf5_wrapper.hdf5_wrapper(f)
        else:
            errors.append(f'{k} file not found: {f}')
            continue

        for p, s in curve:
            if f'{p} Time' not in data[k].keys():
                errors.append(f'Value not found in {k} file: {p}')
                continue

            if f'{p} {s}' not in data[k].keys():
                errors.append(f'Set not found in {k} file: {s}')
                continue

            # Check data sizes in the initial loop to make later logic easier
            if p not in data_sizes:
                data_sizes[p] = {}
            if s not in data_sizes[p]:
                data_sizes[p][s] = {}
            data_sizes[p][s][k] = np.shape(data[k][f'{p} {s}'])

    # Check data diffs
    size_err = '{}_{} values have different sizes: target=({},{},{}) baseline=({},{},{})'
    for p, set_data in data_sizes.items():
        for s, set_sizes in set_data.items():
            if len(set_sizes) == 2:
                xa = data['target'][f'{p} {s}']
                xb = data['baseline'][f'{p} {s}']
                if set_sizes['target'] == set_sizes['baseline']:
                    check_diff(p, s, xa, xb, tolerance, errors)
                else:
                    warnings.append(size_err.format(p, s, *set_sizes['target'], *set_sizes['baseline']))
                    # Check whether the data can be interpolated
                    if (len(set_sizes['baseline']) == 1) or (set_sizes['target'][1:] == set_sizes['baseline'][1:]):
                        warnings.append(f'Interpolating target curve in time: {p}_{s}')
                        ta = data['target'][f'{p} Time']
                        tb = data['baseline'][f'{p} Time']
                        xc = interpolate_values_time(ta, xa, tb)
                        check_diff(p, s, xc, xb, tolerance, errors)
                    else:
                        errors.append(f'Cannot perform a curve check for {p}_{s}')

    # Render figures
    output = os.path.expanduser(output)
    os.makedirs(output, exist_ok=True)
    for p, set_data in data_sizes.items():
        for s, set_sizes in set_data.items():
            curve_check_figure(p, s, data, data_sizes, output, output_n_column, units_time)

    return warnings, errors


def curve_check_parser():
    """
    Build the curve check parser

    Returns:
        argparse.parser: The curve check parser
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="Path to the time history file")
    parser.add_argument("baseline", help="Path to the baseline file")
    parser.add_argument('-c',
                        '--curve',
                        nargs='+',
                        action='append',
                        help='Curves to check (value, setname)',
                        default=[])
    parser.add_argument("-t",
                        "--tolerance",
                        type=float,
                        help=f"The tolerance for curve check diffs, default is 0.",
                        default=0.0)
    parser.add_argument("-w",
                        "--Werror",
                        action="store_true",
                        help="Force all warnings to be errors, default is False.",
                        default=False)
    parser.add_argument("-o",
                        "--output",
                        help="Output figures to this directory",
                        default='./curve_check_figures')
    unit_choices = list(unit_map.keys())
    parser.add_argument("-n",
                        "--n-column",
                        help="Number of columns for the output figure",
                        default=1)
    parser.add_argument("-u",
                        "--units-time",
                        help=f"Time units for plots (default=seconds)",
                        choices=unit_choices,
                        default='seconds')
    return parser


def main():
    """
    Entry point for the curve check script
    """
    parser = curve_check_parser()
    args = parser.parse_args()
    warnings, errors = compare_time_history_curves(args.filename, args.baseline, args.curve, args.tolerance, args.output, args.n_column, args.units_time)

    # Write errors/warnings to the screen
    if args.Werror:
        errors.extend(warnings[:])
        warnings = []

    if len(warnings):
        print('Curve check warnings:')
        print('\n'.join(warnings))

    if len(errors):
        print('Curve check errors:')
        print('\n'.join(errors))
        raise Exception(f'Curve check produced {len(errors)} errors!')


if __name__ == '__main__':
    main()
