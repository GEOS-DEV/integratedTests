import os
import importlib.util
import sys
import argparse
import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
import hdf5_wrapper

unit_map = {
    'milliseconds': 1e-3,
    'seconds': 1.0,
    'minutes': 60.0,
    'hours': 60.0 * 60.0,
    'days': 60.0 * 60.0 * 24.0,
    'years': 60.0 * 60.0 * 24.0 * 365.25
}

DEFAULT_SET_NAME = 'empty_setName'


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


def evaluate_external_script(script, fn, data):
    """
    Evaluate an external script to produce the curve

    Args:
        script (str): Path to a python script
        fn (str): Name of the function to call

    Returns:
        np.ndarray: Curve values
    """
    script = os.path.abspath(script)
    if os.path.isfile(script):
        module_name = os.path.split(script)[1]
        module_name = module_name[:module_name.rfind('.')]
        spec = importlib.util.spec_from_file_location(module_name, script)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        if hasattr(module, fn):
            return getattr(module, fn)(**data)
        else:
            raise Exception(f'External script does not contain the expected function ({fn})')
    else:
        raise FileNotFoundError(f'Could not find script: {script}')


def check_diff(parameter_name, set_name, target, baseline, tolerance, errors, modifier='baseline'):
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
    diff = np.sqrt(np.sum(dx * dx)) / dx.size
    if (diff > tolerance):
        errors.append(
            f'{modifier}_{parameter_name}_{set_name} diff exceeds tolerance: ||t-b||/N={diff}, {modifier}_tolerance={tolerance}'
        )


def curve_check_figure(parameter_name, location_str, set_name, data, data_sizes, output_root, ncol, units_time):
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
    style = {
        'target': {
            'marker': '',
            'linestyle': '-'
        },
        'baseline': {
            'marker': '.',
            'linestyle': ''
        },
        'script': {
            'marker': '',
            'linestyle': ':'
        }
    }
    time_key = f'{parameter_name} Time'
    if set_name == DEFAULT_SET_NAME:
        value_key = f'{parameter_name}'
        location_key = f'{parameter_name} {location_str}'
    else:
        value_key = f'{parameter_name} {set_name}'
        location_key = f'{parameter_name} {location_str} {set_name}'

    s = data_sizes[parameter_name][set_name]
    N = list(s[list(s.keys())[0]])
    nrow = int(np.ceil(float(N[2]) / ncol))
    time_scale = unit_map[units_time]
    horizontal_label = f'Time ({units_time})'

    # Create the figure
    fig = plt.figure(figsize=(8, 6))
    for ii in range(N[2]):
        ax = plt.subplot(nrow, ncol, ii + 1)
        for k in s.keys():
            t = np.squeeze(data[k][time_key]) / time_scale
            x = data[k][value_key][:, :, ii]
            position = data[k][location_key][0, :, 0]

            if (N[1] == 1):
                ax.plot(t, x, label=k, **style[k])

            else:
                cmap = plt.get_cmap('jet')
                if N[0] > N[1]:
                    # Timestep axis
                    for jj in range(N[1]):
                        try:
                            c = cmap(float(jj) / N[1])
                            kwargs = {}
                            if (jj == 0):
                                kwargs['label'] = k
                            ax.plot(t, x[:, jj], color=c, **style[k], **kwargs)
                        except Exception as e:
                            print(f'Error rendering curve {value_key}: {str(e)}')
                else:
                    # Spatial axis
                    horizontal_label = 'X (m)'
                    for jj in range(N[0]):
                        try:
                            c = cmap(float(jj) / N[0])
                            kwargs = {}
                            if (jj == 0):
                                kwargs['label'] = k
                            ax.plot(position, x[jj, :], color=c, **style[k], **kwargs)
                        except Exception as e:
                            print(f'Error rendering curve {value_key}: {str(e)}')

        # Set labels
        ax.set_xlabel(horizontal_label)
        ax.set_ylabel(value_key)
        # ax.set_xlim(t[[0, -1]])
        ax.legend(loc=2)
    plt.tight_layout()
    fig.savefig(os.path.join(output_root, f'{parameter_name}_{set_name}'), dpi=200)


def compare_time_history_curves(fname, baseline, curve, tolerance, output, output_n_column, units_time,
                                script_instructions):
    """
    Compute time history curves

    Args:
        fname (str): Target curve file name
        baseline (str): Baseline curve file name
        curve (list): list containing pairs of value and set names to test
        tolerance (list): Tolerance for curve diffs
        output (str): Path to place output figures
        ncol (int): Number of columns to use in the figure
        units_time (str): Time units for the figure
        script_instructions (list): List of (script, function, parameter, setname) values

    Returns:
        tuple: warnings, errors
    """
    # Setup
    files = {'target': fname, 'baseline': baseline}
    warnings = []
    errors = []
    location_string_options = ['ReferencePosition', 'elementCenter']
    location_strings = {}
    tol = {}

    if len(curve) != len(tolerance):
        raise Exception(
            f'Curvecheck inputs must be of the same length: curves ({len(curve)}) and tolerance ({len(tolerance)})')

    # Load data and check sizes
    data = {}
    data_sizes = {}
    for k, f in files.items():
        if os.path.isfile(f):
            data[k] = hdf5_wrapper.hdf5_wrapper(f).get_copy()
        else:
            errors.append(f'{k} file not found: {f}')
            continue

        for (p, s), t in zip(curve, tolerance):
            if s == DEFAULT_SET_NAME:
                key = f'{p}'
            else:
                key = f'{p} {s}'

            if f'{p} Time' not in data[k].keys():
                errors.append(f'Value not found in {k} file: {p}')
                continue

            if key not in data[k].keys():
                errors.append(f'Set not found in {k} file: {s}')
                continue

            # Check for a location string (this may not be consistent across the same file)
            for kb in data[k].keys():
                for kc in location_string_options:
                    if (kc in kb) and (p in kb):
                        location_strings[p] = kc

            if p not in location_strings:
                test_keys = ', '.join(location_string_options)
                all_keys = ', '.join(data[k].keys())
                errors.append(
                    f'Could not find location string for parameter: {p}, search_options=({test_keys}), all_options={all_keys}'
                )

            # Check data sizes in the initial loop to make later logic easier
            if p not in data_sizes:
                data_sizes[p] = {}
                tol[p] = {}

            if s not in data_sizes[p]:
                data_sizes[p][s] = {}
                tol[p][s] = float(t[0])

            data_sizes[p][s][k] = list(np.shape(data[k][key]))

            # Record requested tolerance
            if p not in tol:
                tol[p] = {}
            if s not in tol[p]:
                tol[p][s] = t

    # Generate script-based curve
    if script_instructions and (len(data) > 0):
        data['script'] = {}
        try:
            for script, fn, p, s in script_instructions:
                k = location_strings[p]
                data['script'][f'{p} Time'] = data['target'][f'{p} Time']
                key = f'{p} {k}'
                key2 = f'{p}'
                if s != DEFAULT_SET_NAME:
                    key += f' {s}'
                    key2 += f' {s}'
                data['script'][key] = data['target'][key]
                data['script'][key2] = evaluate_external_script(script, fn, data['target'])
                data_sizes[p][s]['script'] = list(np.shape(data['script'][key2]))
        except Exception as e:
            errors.append(str(e))

    # Reshape data if necessary so that they have a predictable number of dimensions
    for k in data.keys():
        for p, s in curve:
            key = f'{p}'
            if s != DEFAULT_SET_NAME:
                key += f' {s}'
            if (len(data_sizes[p][s][k]) == 1):
                data[k][key] = np.reshape(data[k][key], (-1, 1, 1))
                data_sizes[p][s][k].append(1)
            elif (len(data_sizes[p][s][k]) == 2):
                data[k][key] = np.expand_dims(data[k][key], -1)
                data_sizes[p][s][k].append(1)

    # Check data diffs
    size_err = '{}_{} values have different sizes: target=({},{},{}) baseline=({},{},{})'
    for p, set_data in data_sizes.items():
        for s, set_sizes in set_data.items():
            key = f'{p}'
            if s != DEFAULT_SET_NAME:
                key += f' {s}'

            if (('baseline' in set_sizes) and ('target' in set_sizes)):
                xa = data['target'][key]
                xb = data['baseline'][key]
                if set_sizes['target'] == set_sizes['baseline']:
                    check_diff(p, s, xa, xb, tol[p][s], errors)
                else:
                    warnings.append(size_err.format(p, s, *set_sizes['target'], *set_sizes['baseline']))
                    # Check whether the data can be interpolated
                    if (len(set_sizes['baseline']) == 1) or (set_sizes['target'][1:] == set_sizes['baseline'][1:]):
                        warnings.append(f'Interpolating target curve in time: {p}_{s}')
                        ta = data['target'][f'{p} Time']
                        tb = data['baseline'][f'{p} Time']
                        xc = interpolate_values_time(ta, xa, tb)
                        check_diff(p, s, xc, xb, tol[p][s], errors)
                    else:
                        errors.append(f'Cannot perform a curve check for {p}_{s}')
            if (('script' in set_sizes) and ('target' in set_sizes)):
                xa = data['target'][key]
                xb = data['script'][key]
                check_diff(p, s, xa, xb, tol[p][s], errors, modifier='script')

    # Render figures
    output = os.path.expanduser(output)
    os.makedirs(output, exist_ok=True)
    for p, set_data in data_sizes.items():
        for s, set_sizes in set_data.items():
            curve_check_figure(p, location_strings[p], s, data, data_sizes, output, output_n_column, units_time)

    return warnings, errors


def curve_check_parser():
    """
    Build the curve check parser

    Returns:
        argparse.parser: The curve check parser
    """

    # Custom action class
    class PairAction(argparse.Action):

        def __call__(self, parser, namespace, values, option_string=None):
            pairs = getattr(namespace, self.dest)
            if len(values) == 1:
                pairs.append((values[0], DEFAULT_SET_NAME))
            elif len(values) == 2:
                pairs.append((values[0], values[1]))
            else:
                raise Exception('Only a single value or a pair of values are expected')

            setattr(namespace, self.dest, pairs)

    # Custom action class
    class ScriptAction(argparse.Action):

        def __call__(self, parser, namespace, values, option_string=None):

            scripts = getattr(namespace, self.dest)
            scripts.append(values)
            N = len(values)
            if (N < 3) or (N > 4):
                raise Exception('The -s option requires 3 or 4 inputs')
            elif N == 3:
                values.append(DEFAULT_SET_NAME)

            setattr(namespace, self.dest, scripts)

    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="Path to the time history file")
    parser.add_argument("baseline", help="Path to the baseline file")
    parser.add_argument('-c',
                        '--curve',
                        nargs='+',
                        action=PairAction,
                        help='Curves to check (value) or (value, setname)',
                        default=[])
    parser.add_argument("-t",
                        "--tolerance",
                        nargs='+',
                        action='append',
                        help=f"The tolerance for each curve check diffs (||x-y||/N)",
                        default=[])
    parser.add_argument("-w",
                        "--Werror",
                        action="store_true",
                        help="Force all warnings to be errors, default is False.",
                        default=False)
    parser.add_argument("-o", "--output", help="Output figures to this directory", default='./curve_check_figures')
    unit_choices = list(unit_map.keys())
    parser.add_argument("-n", "--n-column", help="Number of columns for the output figure", default=1)
    parser.add_argument("-u",
                        "--units-time",
                        help=f"Time units for plots (default=seconds)",
                        choices=unit_choices,
                        default='seconds')
    parser.add_argument("-s",
                        "--script",
                        nargs='+',
                        action=ScriptAction,
                        help='Python script instructions (path, function, value, setname)',
                        default=[])

    return parser


def main():
    """
    Entry point for the curve check script
    """
    parser = curve_check_parser()
    args = parser.parse_args()
    warnings, errors = compare_time_history_curves(args.filename, args.baseline, args.curve, args.tolerance,
                                                   args.output, args.n_column, args.units_time, args.script)

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
