
import os
import importlib.util
import sys
import re
import argparse
import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
import hdf5_wrapper
import h5py

def parse_log_file( fname ):
    """
    Parses the log file and creates an hdf5 with number of linear and nonlinear iterations per time-step
    
    Args: fname (str): name of the log file to parse

    Returns: output_fileName (str):
             errors:
    """
    # Define regular expressions
    cycle_pattern = r"\d+\s*:\s*Time: [\d.e+-]+ s, dt: [\d.e+-]+ s, Cycle: (\d+)"
    config_and_nnlinear_iter_pattern = r"\d+\s*:\s*Attempt:\s*(\d+),\s*ConfigurationIter:\s*(\d+),\s*NewtonIter:\s*(\d+)"
    linear_iter_pattern = r"\d+\s*:\s*Last LinSolve\(iter,res\) = \(\s*(\d+),\s*([\d.e+-]+)\s*\) ;"

    # Initialize variables to store the extracted data
    data = {}

    with open(fname, 'r') as file:
        for line in file:
            # Match Cycle number
            cycle_match = re.match(cycle_pattern, line)
            if cycle_match:
                cycle_number = cycle_match.group(1)
                data[cycle_number] = {
                    'Attempts': {}
                }
            
            # Match ConfigurationIter data
            config_iter_match = re.match(config_and_nnlinear_iter_pattern, line)
            if config_iter_match and cycle_number:
                attempt, config_iter, newton_iter = config_iter_match.groups()
                if int(newton_iter) > 0:
                    attempt_data = data[cycle_number]['Attempts'].get(attempt, {})
                    config_data = attempt_data.get('ConfigurationIters', [])
                    config_data.append({
                        'ConfigurationIter': config_iter,
                        'NewtonIters': {}
                    })
                    attempt_data['ConfigurationIters'] = config_data
                    data[cycle_number]['Attempts'][attempt] = attempt_data

            # Match Iteration data
            iteration_match = re.match(linear_iter_pattern, line)
            if iteration_match and cycle_number and attempt and config_iter:
                num_iterations = int(iteration_match.group(1))
                attempt_data = data[cycle_number]['Attempts'][attempt]
                config_data = attempt_data['ConfigurationIters']
                config_iter_data = config_data[-1]
                config_iter_data['NewtonIters'][newton_iter] = num_iterations

    # Create an HDF5 file for storing the data
    output_fileName = os.path.join(os.path.dirname(fname), 'extracted_performance_data.h5')
    with h5py.File(output_fileName, 'w') as hdf5_file:
        for cycle, cycle_data in data.items():
            cycle_group = hdf5_file.create_group(f'Cycle_{cycle}')
            for attempt, attempt_data in cycle_data['Attempts'].items():
                attempt_group = cycle_group.create_group(f'Attempt_{attempt}')
                for config_iter_data in attempt_data['ConfigurationIters']:
                    config_iter_group = attempt_group.create_group(f'ConfigIter_{config_iter_data["ConfigurationIter"]}')
                    newton_iter_list = []
                    linear_iter_list = []
                    for newton_iter, num_iterations in config_iter_data['NewtonIters'].items():
                        newton_iter_list.append(int(newton_iter))
                        linear_iter_list.append(num_iterations)
                    
                    matrix_data = np.column_stack((newton_iter_list, linear_iter_list))
                    config_iter_group.create_dataset('NewtonAndLinearIterations', data=matrix_data)

    print(f'Data has been saved to {output_fileName}')                    

    errors = []                

    return output_fileName, errors        

def load_data(fname):
    """
    Args: 
        fname (str):
        errors (list): 

    Returns:
        tuple: data, errors          
    """
    data = {}
    if os.path.isfile(fname):
        data = hdf5_wrapper.hdf5_wrapper(fname).get_copy()
    else:
       raise Exception(f'file {fname} not found. If baselines do not exist you may simply need to rebaseline this case.')
    return data

# def plot_performance_curves():
#     """
#     """

def compare_performance_curves( fname, baseline, tolerances, output ):
    """
    Compute time history curves

    Args:
        fname (str): Target curve file name
        baseline (str): Baseline curve file name
        tolerances (list): Tolerance for nonlinear and linear iterations
        output (str): Path to place output figures
    Returns:
        tuple: warnings, errors
    """
    # Setup
    warnings = []
    errors = []

    newton_iterations_tolerance, linear_iterations_tolerance = tolerances

    # Load data
    target_data   = load_data( fname )
    baseline_data = load_data( baseline )

    # Check if the number of cycles is the same
    target_cycles   = set(target_data.keys())
    baseline_cycles = set(baseline_data.keys())
    if target_cycles != baseline_cycles:
        errors.append(f'Number of cycles is different.')

    # Loop over each cycle
    for cycle in target_cycles:
        target_num_attempts = set(target_data[cycle].keys())
        baseline_num_attempts = set(baseline_data[cycle].keys())
        
        # Check if the number of attempts is the same for this cycle
        if target_num_attempts != baseline_num_attempts:
            errors.append(f'Number of attempts for Cycle {cycle} is different.')
        
        # Loop over each attempt
        for attempt in target_num_attempts:
            target_config_iters = set(target_data[cycle][attempt].keys())
            baeline_config_iters = set(baseline_data[cycle][attempt].keys())
            
            # Check if the number of ConfigurationIters is the same for this Attempt
            if target_config_iters != baeline_config_iters:
                errors.append(f'Number of ConfigurationIters for Cycle {cycle}, Attempt {attempt} is different.')

            # Loop over each ConfigurationIter
            for config_iter in target_config_iters:
                # Check if the NewtonAndLinearIterations are within tolerance
                target_iterations = np.array(target_data[cycle][attempt][config_iter]['NewtonAndLinearIterations'])
                baseline_iterations = np.array(baseline_data[cycle][attempt][config_iter]['NewtonAndLinearIterations'])
                
                newton_diff = np.abs(target_iterations[:, 0] - baseline_iterations[:, 0])
                linear_diff = np.abs(target_iterations[:, 1] - baseline_iterations[:, 1])

                if (np.any(newton_diff > newton_iterations_tolerance * target_iterations[:, 0]) or
                    np.any(linear_diff > linear_iterations_tolerance * target_iterations[:, 1])):
                    errors.append(f'Differences found in NewtonAndLinearIterations for Cycle {cycle}, Attempt {attempt}, ConfigurationIter {config_iter}.')

    return warnings, errors

def performance_check_parser():
    """
    Build the curve check parser

    Returns:
        argparse.parser: The performance check parser
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="Path to the log file")
    parser.add_argument("baseline", help="Path to the baseline file")
    parser.add_argument("-t",
                        "--tolerance",
                        nargs='+',
                        action='append',
                        help=f"The tolerance for nonlinear and linear iterations",
                        default=[])
    parser.add_argument("-o",
                        "--output",
                        help="Output figures to this directory",
                        default='./performance_check_figures')
    return parser


def main():
    """
    Entry point for the performance check script
    """
    parser = performance_check_parser()
    args = parser.parse_args()
    fname, parsingErrors = parse_log_file( args.filename )
    
    # We raise immediately if there is any issue while parsing
    if len(parsingErrors):
        print('\n'.join(parsingErrors))
        raise Exception(f'Performance check error while parsing log file.')

    warnings, errors = compare_performance_curves( fname, args.baseline, args.tolerance, args.output )

    if len(warnings):
        print('Performance check warnings:')
        print('\n'.join(warnings))

    if len(errors):
        print('Performance check errors:')
        print('\n'.join(errors))
        raise Exception(f'Performance check produced {len(errors)} errors!')

if __name__ == '__main__':
    main()
