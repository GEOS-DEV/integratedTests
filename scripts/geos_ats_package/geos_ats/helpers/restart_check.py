import h5py    # type: ignore[import]
from mpi4py import MPI    # type: ignore[import]
import numpy as np    # type: ignore[import]
import sys
import os
import re
import argparse
import logging
from pathlib import Path
try:
    from geos_ats.helpers.permute_array import permuteArray    # type: ignore[import]
except ImportError:
    # Fallback method to be used if geos_ats isn't found
    from permute_array import permuteArray    # type: ignore[import]

RTOL_DEFAULT = 0.0
ATOL_DEFAULT = 0.0
EXCLUDE_DEFAULT = [".*/commandLine", ".*/schema$", ".*/globalToLocalMap", ".*/timeHistoryOutput.*/restart"]
logger = logging.getLogger('geos_ats')


def write(output, msg):
    """
    Write MSG to both stdout and OUTPUT.
    OUTPUT [in/out]: File stream to write to.
    MSG [in]: Message to write.
    """
    msg = str(msg)
    sys.stdout.write(msg)
    sys.stdout.flush()
    output.write(msg)


def h5PathJoin(p1, p2):
    if p1 == "/":
        return "/" + p2
    if p1 == "":
        return p2

    return p1 + "/" + p2


class FileComparison(object):
    """
    Class that compares two hdf5 files.
    """

    def __init__(self,
                 file_path,
                 baseline_path,
                 rtol,
                 atol,
                 regex_expressions,
                 output,
                 warnings_are_errors,
                 skip_missing,
                 diff_file=None):
        """
        FILE_PATH [in]: The path of the first file to compare.
        BASELINE_PATH [in]: The path of the baseline file to compare against.
        RTOL [in]: The relative tolerance used in comparing floating point numbers.
        ATOL [in]: The absolute tolerance used in comparing floating point numbers.
        REGEX_EXPRESSIONS [in]: A list of compiled regex expressions that match hdf5 groups and datasets to exclude.
        OUTPUT [in/out]: The file stream to write output to.
        WARNIGNS_ARE_ERRORS [in]: Boolean specifying whether warnings are to be treated as errors.
        """
        self.file_path = file_path
        self.baseline_path = baseline_path
        self.rtol = rtol
        self.atol = atol
        self.regex_expressions = regex_expressions
        self.output = output
        self.warnings_are_errors = warnings_are_errors
        self.skip_missing = skip_missing
        self.diff_file = diff_file
        self.different = False

        assert (self.rtol >= 0.0)
        assert (self.atol >= 0.0)

    def filesDiffer(self):
        try:
            with h5py.File(self.file_path, "r") as file, h5py.File(self.baseline_path, "r") as base_file:
                self.file_path = file.filename
                self.baseline_path = base_file.filename
                self.output.write("\nRank %s is comparing %s with %s \n" %
                                  (MPI.COMM_WORLD.Get_rank(), self.file_path, self.baseline_path))
                self.compareGroups(file, base_file)

        except IOError as e:
            self.logger.debug(e)
            self.output.write(str(e))
            self.different = True

        return self.different

    def add_links(self, path, message):
        # When comparing the root groups self.diff_file is none.
        if self.diff_file is None:
            return

        base_name = os.path.basename(self.file_path)
        diff_group_name = base_name + "/" + path
        diff_group = self.diff_file.create_group(diff_group_name)
        diff_group.create_dataset("message", data=message)
        diff_group["run"] = h5py.ExternalLink(self.file_path, path)
        diff_group["baseline"] = h5py.ExternalLink(self.baseline_path, path)

    def errorMsg(self, path, message, add_to_diff=False):
        """
        Issue an error which occurred at PATH in the files with the contents of MESSAGE.
        Sets self.different to True and rites the error to both stdout and OUTPUT.

        PATH [in]: The path in the files at which the error occurred.
        MESSAGE [in]: The error message.
        """
        self.different = True
        msg = '*' * 80 + "\n"
        msg += "Error: %s\n" % path
        msg += "\t" + "\n\t".join(message.split("\n"))[:-1]
        msg += '*' * 80 + "\n"
        self.output.write(msg)

        if add_to_diff:
            self.add_links(path, message)

    def warningMsg(self, path, message):
        """
        Issue a warning which occurred at PATH in the files with the contents of MESSAGE.
        Writes the warning to both stdout and OUTPUT. If WARNINGS_ARE_ERRORS then this
        is a wrapper around errorMsg.

        PATH [in]: The path in the files at which the warning occurred.
        MESSAGE [in]: The warning message.
        """
        if self.warnings_are_errors:
            return self.errorMsg(path, message)

        msg = '*' * 80 + "\n"
        msg += "Warning: %s\n" % path
        msg += "\t" + "\n\t".join(message.split("\n"))[:-1]
        msg += '*' * 80 + "\n"
        self.output.write(msg)

    def isExcluded(self, path):
        """
        Return True iff path matches any of the regex expressions in self.regex_expressions.

        PATH [in]: The path to match.
        """
        for regex in self.regex_expressions:
            if regex.match(path) is not None:
                return True
        return False

    def compareFloatScalars(self, path, val, base_val):
        """
        Compare floating point scalars.

        PATH [in]: The path at which the comparison occurs.
        VAL [in]: The value to compare.
        BASE_VAL [in]: The baseline value to compare against.
        """
        dif = abs(val - base_val)
        if dif > self.atol and dif > self.rtol * abs(base_val):
            msg = "Scalar values of types %s and %s differ: %s, %s.\n" % (val.dtype, base_val.dtype, val, base_val)
            self.errorMsg(path, msg, True)

    def compareIntScalars(self, path, val, base_val):
        """
        Compare integer scalars.

        PATH [in]: The path at which the comparison occurs.
        VAL [in]: The value to compare.
        BASE_VAL [in]: The baseline value to compare against.
        """
        if val != base_val:
            msg = "Scalar values of types %s and %s differ: %s, %s.\n" % (val.dtype, base_val.dtype, val, base_val)
            self.errorMsg(path, msg, True)

    def compareStringScalars(self, path, val, base_val):
        """
        Compare string scalars.

        PATH [in]: The path at which the comparison occurs.
        VAL [in]: The value to compare.
        BASE_VAL [in]: The baseline value to compare against.
        """
        if val != base_val:
            msg = "Scalar values of types %s and %s differ: %s, %s.\n" % (val.dtype, base_val.dtype, val, base_val)
            self.errorMsg(path, msg, True)

    def compareFloatArrays(self, path, arr, base_arr):
        """
        Compares two arrays ARR and BASEARR of floating point values.
        Entries x1 and x2 are  considered equal iff:

            |x1 - x2| <= ATOL * ( 1 + max(|x2|) )
            - or -
            |x1 - x2| <= RTOL * |x2|.

        To measure the degree of difference a scaling factor q
        is introduced. The goal is now to minimize q such that:

            |x1 - x2| <= ATOL * ( 1 + max(|x2|) ) * q
            - or -
            |x1 - x2| <= RTOL * |x2| * q.

        If RTOL * |x2| > ATOL * ( 1 + max(|x2|) )
            q = |x1 - x2| / (RTOL * |x2|)
        else
            q = |x1 - x2| / ( ATOL * ( 1 + max(|x2|) ) ).

        If the maximum value of q over all the
        entries is greater than 1.0 then the arrays are considered
        different and an error message is produced.

        PATH [in]: The path at which the comparison takes place.
        ARR [in]: The hdf5 Dataset to compare.
        BASE_ARR [in]: The hdf5 Dataset to compare against.
        """
        # If we have zero tolerance then just call the compareIntArrays function.
        if self.rtol == 0.0 and self.atol == 0.0:
            return self.compareIntArrays(path, arr, base_arr)

        # If the shapes are different they can't be compared.
        if arr.shape != base_arr.shape:
            msg = "Datasets have different shapes and therefore can't be compared: %s, %s.\n" % (arr.shape,
                                                                                                 base_arr.shape)
            self.errorMsg(path, msg, True)
            return

        # First create a copy of the data in the datasets.
        arr_cpy = np.copy(arr)
        base_arr_cpy = np.copy(base_arr)

        # Now compute the difference and store the result in ARR1_CPY
        # which is appropriately renamed DIFFERENCE.
        difference = np.subtract(arr, base_arr, out=arr_cpy)
        np.abs(difference, out=difference)

        # Take the absolute value of BASE_ARR_CPY and rename it to ABS_BASE_ARR
        abs_base_arr = np.abs(base_arr_cpy, out=base_arr_cpy)

        #        max_abs_base_arr = np.max( abs_base_arr )
        #         comm = MPI.COMM_WORLD
        #         size = comm.Get_size()
        #         if size > 1:
        #             max_abs_base_arr = comm.allreduce(max_abs_base_arr, op=MPI.MAX)

        #        absTol = (1.0 + max_abs_base_arr) * self.atol
        absTol = self.atol

        # Get the indices of the max absolute and relative error
        max_absolute_index = np.unravel_index(np.argmax(difference), difference.shape)

        relative_difference = difference / (abs_base_arr + 1e-20)

        # If the absolute tolerance is not zero, replace all nan's with zero.
        if self.atol != 0:
            relative_difference = np.nan_to_num(relative_difference, 0)

        max_relative_index = np.unravel_index(np.argmax(relative_difference), relative_difference.shape)

        if self.rtol != 0.0:
            relative_difference /= self.rtol

        if self.rtol == 0.0:
            difference /= absTol
            q = difference
            absolute_limited = np.ones(q.shape, dtype=bool)
        elif self.atol == 0.0:
            q = relative_difference
            absolute_limited = np.zeros(q.shape, dtype=bool)
        else:
            # Multiply ABS_BASE_ARR by RTOL and rename it to RTOL_ABS_BASE
            rtol_abs_base = np.multiply(self.rtol, abs_base_arr, out=abs_base_arr)

            # Calculate which entries are limited by the relative tolerance.
            relative_limited = rtol_abs_base > absTol

            # Rename DIFFERENCE to Q where we will store the scaling parameter q.
            q = difference
            q[relative_limited] = relative_difference[relative_limited]

            # Compute q for the entries which are limited by the absolute tolerance.
            absolute_limited = np.logical_not(relative_limited, out=relative_limited)
            q[absolute_limited] /= absTol

        # If the maximum q value is greater than 1.0 than issue an error.
        if np.max(q) > 1.0:
            offenders = np.greater(q, 1.0)
            n_offenders = np.sum(offenders)

            absolute_offenders = np.logical_and(offenders, absolute_limited, out=offenders)
            q_num_absolute = np.sum(absolute_offenders)
            if q_num_absolute > 0:
                absolute_qs = q * absolute_offenders
                q_max_absolute = np.max(absolute_qs)
                q_max_absolute_index = np.unravel_index(np.argmax(absolute_qs), absolute_qs.shape)
                q_mean_absolute = np.mean(absolute_qs)
                q_std_absolute = np.std(absolute_qs)

            offenders = np.greater(q, 1.0, out=offenders)
            relative_limited = np.logical_not(absolute_limited, out=absolute_limited)
            relative_offenders = np.logical_and(offenders, relative_limited, out=offenders)
            q_num_relative = np.sum(relative_offenders)
            if q_num_relative > 0:
                relative_qs = q * relative_offenders
                q_max_relative = np.max(relative_qs)
                q_max_relative_index = np.unravel_index(np.argmax(relative_qs), q.shape)
                q_mean_relative = np.mean(relative_qs)
                q_std_relative = np.std(relative_qs)

            message = "Arrays of types %s and %s have %d values of which %d fail both the relative and absolute tests.\n" % (
                arr.dtype, base_arr.dtype, offenders.size, n_offenders)
            message += "\tMax absolute difference is at index %s: value = %s, base_value = %s\n" % (
                max_absolute_index, arr[max_absolute_index], base_arr[max_absolute_index])
            message += "\tMax relative difference is at index %s: value = %s, base_value = %s\n" % (
                max_relative_index, arr[max_relative_index], base_arr[max_relative_index])
            message += "Statistics of the q values greater than 1.0 defined by absolute tolerance: N = %d\n" % q_num_absolute
            if q_num_absolute > 0:
                message += "\tmax = %s, mean = %s, std = %s\n" % (q_max_absolute, q_mean_absolute, q_std_absolute)
                message += "\tmax is at index %s, value = %s, base_value = %s\n" % (
                    q_max_absolute_index, arr[q_max_absolute_index], base_arr[q_max_absolute_index])
            message += "Statistics of the q values greater than 1.0 defined by relative tolerance: N = %d\n" % q_num_relative
            if q_num_relative > 0:
                message += "\tmax = %s, mean = %s, std = %s\n" % (q_max_relative, q_mean_relative, q_std_relative)
                message += "\tmax is at index %s, value = %s, base_value = %s\n" % (
                    q_max_relative_index, arr[q_max_relative_index], base_arr[q_max_relative_index])
            self.errorMsg(path, message, True)

    def compareIntArrays(self, path, arr, base_arr):
        """
        Compare two integer datasets. Exact equality is used as the acceptance criteria.

        PATH [in]: The path at which the comparison takes place.
        ARR [in]: The hdf5 Dataset to compare.
        BASE_ARR [in]: The hdf5 Dataset to compare against.
        """
        # If the shapes are different they can't be compared.
        if arr.shape != base_arr.shape:
            msg = "Datasets have different shapes and therefore can't be compared: %s, %s.\n" % (arr.shape,
                                                                                                 base_arr.shape)
            self.errorMsg(path, msg, True)
            return

        # Create a copy of the arrays.

        # Calculate the absolute difference.
        difference = np.subtract(arr, base_arr)
        np.abs(difference, out=difference)

        offenders = difference != 0.0
        n_offenders = np.sum(offenders)

        if n_offenders != 0:
            max_index = np.unravel_index(np.argmax(difference), difference.shape)
            max_difference = difference[max_index]
            offenders_mean = np.mean(difference[offenders])
            offenders_std = np.std(difference[offenders])

            message = "Arrays of types %s and %s have %s values of which %d have differing values.\n" % (
                arr.dtype, base_arr.dtype, offenders.size, n_offenders)
            message += "Statistics of the differences greater than 0:\n"
            message += "\tmax_index = %s, max = %s, mean = %s, std = %s\n" % (max_index, max_difference, offenders_mean,
                                                                              offenders_std)
            self.errorMsg(path, message, True)

    def compareStringArrays(self, path, arr, base_arr):
        """
        Compare two string datasets. Exact equality is used as the acceptance criteria.

        PATH [in]: The path at which the comparison takes place.
        ARR [in]: The hdf5 Dataset to compare.
        BASE_ARR [in]: The hdf5 Dataset to compare against.
        """
        if arr.shape != base_arr.shape or np.any(arr[:] != base_arr[:]):
            message = "String arrays differ.\n"
            message += "String to compare: %s\n" % "".join(arr[:])
            message += "Baseline string  : %s\n" % "".join(base_arr[:])
            self.errorMsg(path, message, True)

    def compareData(self, path, arr, base_arr):
        """
        Compare the numerical portion of two datasets.

        PATH [in]: The path at which the comparison takes place.
        ARR [in]: The hdf5 Dataset to compare.
        BASE_ARR [in]: The hdf5 Dataset to compare against.
        """
        # Get the type of comparison to do.
        np_floats = set(['f', 'c'])
        np_ints = set(['?', 'b', 'B', 'i', 'u', 'm', 'M', 'V'])
        np_numeric = np_floats | np_ints
        np_strings = set(['S', 'a', 'U'])

        int_compare = arr.dtype.kind in np_ints and base_arr.dtype.kind in np_ints
        float_compare = not int_compare and (arr.dtype.kind in np_numeric and base_arr.dtype.kind in np_numeric)
        string_compare = arr.dtype.kind in np_strings and base_arr.dtype.kind in np_strings

        # If the datasets have different types issue a warning.
        if arr.dtype != base_arr.dtype:
            msg = "Datasets have different types: %s, %s.\n" % (arr.dtype, base_arr.dtype)
            self.warningMsg(path, msg)

        # Handle empty datasets
        if arr.shape is None and base_arr.shape is None:
            return
        if arr.size is None and base_arr.size is None:
            return
        if arr.size == 0 and base_arr.size == 0:
            return
        elif arr.size is None and base_arr.size is not None:
            self.errorMsg(path, "File to compare has an empty dataset where the baseline's dataset is not empty.\n")
        elif base_arr.size is None and arr.size is not None:
            self.warningMsg(path, "Baseline has an empty dataset where the file to compare's dataset is not empty.\n")

        # If either of the datasets is a scalar convert it to an array.
        if arr.shape == ():
            arr = np.array([arr])
        if base_arr.shape == ():
            base_arr = np.array([base_arr])

        # If the datasets only contain one value call the compare scalar functions.
        if arr.size == 1 and base_arr.size == 1:
            val = arr[:].flat[0]
            base_val = base_arr[:].flat[0]
            if float_compare:
                return self.compareFloatScalars(path, val, base_val)
            elif int_compare:
                return self.compareIntScalars(path, val, base_val)
            elif string_compare:
                return self.compareStringScalars(path, val, base_val)
            else:
                return self.warningMsg(path, "Unrecognized type combination: %s %s.\n" % (arr.dtype, base_arr.dtype))

        # Do the actual comparison.
        if float_compare:
            return self.compareFloatArrays(path, arr, base_arr)
        elif int_compare:
            return self.compareIntArrays(path, arr, base_arr)
        elif string_compare:
            return self.compareStringArrays(path, arr, base_arr)
        else:
            return self.warningMsg(path, "Unrecognized type combination: %s %s.\n" % (arr.dtype, base_arr.dtype))

    def compareAttributes(self, path, attrs, base_attrs):
        """
        Compare two sets of attributes.

        PATH [in]: The path at which the comparison takes place.
        ATTRS [in]: The hdf5 AttributeManager to compare.
        BASE_ATTRS [in]: The hdf5 AttributeManager to compare against.
        """
        for attrName in set(list(attrs.keys()) + list(base_attrs.keys())):
            if attrName not in attrs:
                msg = "Attribute %s is in the baseline file but not the file to compare.\n" % attrName
                self.errorMsg(path, msg)
                continue
            if attrName not in base_attrs:
                msg = "Attribute %s is in the file to compare but not the baseline file.\n" % attrName
                self.warningMsg(path, msg)
                continue

            attrsPath = path + ".attrs[" + attrName + "]"
            self.compareData(attrsPath, attrs[attrName], base_attrs[attrName])

    def compareDatasets(self, dset, base_dset):
        """
        Compare two datasets.

        DSET [in]: The Dataset to compare.
        BASE_DSET [in]: The Dataset to compare against.
        """
        assert isinstance(dset, h5py.Dataset)
        assert isinstance(base_dset, h5py.Dataset)

        path = dset.name
        self.compareAttributes(path, dset.attrs, base_dset.attrs)

        self.compareData(path, dset, base_dset)

    def canCompare(self, group, base_group, name):
        name_in_group = name in group
        name_in_base_group = name in base_group

        if not name_in_group and not name_in_base_group:
            return False

        elif self.isExcluded(h5PathJoin(group.name, name)):
            return False

        if not name_in_group:
            msg = "Group has a child '%s' in the baseline file but not the file to compare.\n" % name
            if not self.skip_missing:
                self.errorMsg(base_group.name, msg)
            return False

        if not name_in_base_group:
            msg = "Group has a child '%s' in the file to compare but not the baseline file.\n" % name
            if not self.skip_missing:
                self.errorMsg(group.name, msg)
            return False

        return True

    def compareLvArrays(self, group, base_group, other_children_to_check):
        if self.canCompare(group, base_group, "__dimensions__") and self.canCompare(
                group, base_group, "__permutation__") and self.canCompare(group, base_group, "__values__"):
            other_children_to_check.remove("__dimensions__")
            other_children_to_check.remove("__permutation__")
            other_children_to_check.remove("__values__")

            dimensions = group["__dimensions__"][:]
            base_dimensions = base_group["__dimensions__"][:]

            if len(dimensions.shape) != 1:
                msg = "The dimensions of an LvArray must itself be a 1D array not %s\n" % len(dimensions.shape)
                self.errorMsg(group.name, msg)

            if dimensions.shape != base_dimensions.shape or np.any(dimensions != base_dimensions):
                msg = "Cannot compare LvArrays because they have different dimensions. Dimensions = %s, base dimensions = %s\n" % (
                    dimensions, base_dimensions)
                self.errorMsg(group.name, msg)
                return True

            permutation = group["__permutation__"][:]
            base_permutation = base_group["__permutation__"][:]

            if len(permutation.shape) != 1:
                msg = "The permutation of an LvArray must itself be a 1D array not %s\n" % len(permutation.shape)
                self.errorMsg(group.name, msg)

            if permutation.shape != dimensions.shape or np.any(np.sort(permutation) != np.arange(permutation.size)):
                msg = "LvArray in the file to compare has an invalid permutation. Dimensions = %s, Permutation = %s\n" % (
                    dimensions, permutation)
                self.errorMsg(group.name, msg)
                return True

            if base_permutation.shape != base_dimensions.shape or np.any(
                    np.sort(base_permutation) != np.arange(base_permutation.size)):
                msg = "LvArray in the baseline has an invalid permutation. Dimensions = %s, Permutation = %s\n" % (
                    base_dimensions, base_permutation)
                self.errorMsg(group.name, msg)
                return True

            values = group["__values__"][:]
            base_values = base_group["__values__"][:]

            values, errorMsg = permuteArray(values, dimensions, permutation)
            if values is None:
                msg = "Failed to permute the LvArray: %s\n" % errorMsg
                self.errorMsg(group.name, msg)
                return True

            base_values, errorMsg = permuteArray(base_values, base_dimensions, base_permutation)
            if base_values is None:
                msg = "Failed to permute the baseline LvArray: %s\n" % errorMsg
                self.errorMsg(group.name, msg)
                return True

            self.compareData(group.name, values, base_values)
            return True

        return False

    def compareGroups(self, group, base_group):
        """
        Compare hdf5 groups.
        GROUP [in]: The Group to compare.
        BASE_GROUP [in]: The Group to compare against.
        """
        assert (isinstance(group, (h5py.Group, h5py.File)))
        assert (isinstance(base_group, (h5py.Group, h5py.File)))

        path = group.name

        # Compare the attributes in the two groups.
        self.compareAttributes(path, group.attrs, base_group.attrs)

        children_to_check = set(list(group.keys()) + list(base_group.keys()))
        self.compareLvArrays(group, base_group, children_to_check)

        # Compare the sub groups and datasets.
        for name in children_to_check:
            if self.canCompare(group, base_group, name):
                item1 = group[name]
                item2 = base_group[name]
                if not isinstance(item1, type(item2)):
                    msg = "Child %s has differing types in the file to compare and the baseline: %s, %s.\n" % (
                        name, type(item1), type(item2))
                    self.errorMsg(path, msg)
                    continue

                if isinstance(item1, h5py.Group):
                    self.compareGroups(item1, item2)
                elif isinstance(item1, h5py.Dataset):
                    self.compareDatasets(item1, item2)
                else:
                    self.warningMsg(path, "Child %s has unknown type: %s.\n" % (name, type(item1)))


def findFiles(file_pattern, baseline_pattern, comparison_args):
    # Find the matching files.
    file_path = findMaxMatchingFile(file_pattern)
    if file_path is None:
        raise ValueError("No files found matching %s." % file_pattern)

    baseline_path = findMaxMatchingFile(baseline_pattern)
    if baseline_path is None:
        raise ValueError("No files found matching %s." % baseline_pattern)

    # Get the output path.
    output_base_path = os.path.splitext(file_path)[0]
    output_path = output_base_path + ".restartcheck"

    # Open the output file and diff file
    files_to_compare = None
    with open(output_path, 'w') as output_file:
        comparison_args["output"] = output_file
        writeHeader(file_pattern, file_path, baseline_pattern, baseline_path, comparison_args)

        # Check if comparing root files.
        if file_path.endswith(".root") and baseline_path.endswith(".root"):
            p = [re.compile("/file_pattern"), re.compile("/protocol/version")]
            comp = FileComparison(file_path, baseline_path, 0.0, 0.0, p, output_file, True, False)
            if comp.filesDiffer():
                write(output_file, "The root files are different, cannot compare data files.\n")
                return output_base_path, None
            else:
                write(output_file, "The root files are similar.\n")

            # Get the number of files and the file patterns.
            # We know the number of files are the same from the above comparison.
            with h5py.File(file_path, "r") as f:
                numberOfFiles = f["number_of_files"][0]
                file_data_pattern = "".join(f["file_pattern"][:].tobytes().decode('ascii')[:-1])

            with h5py.File(baseline_path, "r") as f:
                baseline_data_pattern = "".join(f["file_pattern"][:].tobytes().decode('ascii')[:-1])

            # Get the paths to the data files.
            files_to_compare = []
            for i in range(numberOfFiles):
                path_to_data = os.path.join(os.path.dirname(file_path), file_data_pattern % i)
                path_to_baseline_data = os.path.join(os.path.dirname(baseline_path), baseline_data_pattern % i)
                files_to_compare += [(path_to_data, path_to_baseline_data)]

        else:
            files_to_compare = [(file_path, baseline_path)]

    return output_base_path, files_to_compare


def gatherOutput(output_file, output_base_path, n_files):
    for i in range(n_files):
        output_path = "%s.%d.restartcheck" % (output_base_path, i)
        with open(output_path, "r") as file:
            for line in file:
                write(output_file, line)


def findMaxMatchingFile(file_path):
    """
    Given a path FILE_PATH where the base name of FILE_PATH is treated as a regular expression
    find and return the path of the greatest matching file/folder or None if no match is found.

    FILE_PATH [in]: The pattern to match.

    Examples:
        ".*" will return the file/folder with the greatest name in the current directory.

        "test/plot_*.hdf5" will return the file with the greatest name in the ./test directory
        that begins with "plot_" and ends with ".hdf5".
    """
    file_directory, pattern = os.path.split(file_path)
    if file_directory == "":
        file_directory = "."

    if not os.path.isdir(file_directory):
        return None

    pattern = re.compile(pattern)
    max_match = ""
    for file in os.listdir(file_directory):
        if pattern.match(file) is not None:
            max_match = max(file, max_match)

    if max_match == "":
        return None

    return os.path.join(file_directory, max_match)


def writeHeader(file_pattern, file_path, baseline_pattern, baseline_path, args):
    """
    Write the header.

    FILE_PATTERN [in]: The pattern used to find the file to compare.
    FILE_PATH [in]: The path to the file to compare.
    BASELINE_PATTERN [in]: The pattern used to find the file to compare against.
    BASELINE_PATH [in]: THE path to the file to compare against.
    ARGS [in]: A dictionary of arguments to FileComparison.
    """
    output = args["output"]
    msg = "Comparison of file %s from pattern %s\n" % (file_path, file_pattern)
    msg += "Baseline file %s from pattern %s\n" % (baseline_path, baseline_pattern)
    msg += "Relative tolerance: %s\n" % args["rtol"]
    msg += "Absolute tolerance: %s\n" % args["atol"]
    msg += "Output file: %s\n" % output.name
    msg += "Excluded groups: %s\n" % list(map(lambda e: e.pattern, args["regex_expressions"]))
    msg += "Warnings are errors: %s\n\n" % args["warnings_are_errors"]
    write(output, msg)


def main():
    """
    Parses the command line arguments and executes the proper comparison. Writes output to
    both stdout and a '%s.restartcheck' file where the first part is the path of the file to compare.

    Example:
        The file to compare is ./a/b/c.hdf5 the output will be a ./a/b/c.restartcheck file.
    """

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    n_ranks = comm.Get_size()

    parser = argparse.ArgumentParser()
    parser.add_argument("file_pattern", help="The pattern used to find the file to compare.")
    parser.add_argument("baseline_pattern", help="The pattern used to find the baseline file.")
    parser.add_argument("-r",
                        "--relative",
                        type=float,
                        help="The relative tolerance for floating point differences, default is %s." % RTOL_DEFAULT,
                        default=RTOL_DEFAULT)
    parser.add_argument("-a",
                        "--absolute",
                        type=float,
                        help="The absolute tolerance for floating point differences, default is %s." % ATOL_DEFAULT,
                        default=ATOL_DEFAULT)
    parser.add_argument("-e",
                        "--exclude",
                        action='append',
                        help="Regular expressions specifying which groups to skip, default is %s." % EXCLUDE_DEFAULT,
                        default=EXCLUDE_DEFAULT)
    parser.add_argument("-m",
                        "--skip-missing",
                        action="store_true",
                        help="Ignore values that are missing from either the baseline or target file.",
                        default=False)
    parser.add_argument("-w",
                        "--Werror",
                        action="store_true",
                        help="Force all warnings to be errors, default is False.",
                        default=False)
    args = parser.parse_args()

    # Check the command line arguments
    if args.relative < 0.0:
        raise ValueError("Relative tolerance cannot be less than 0.0.")
    if args.absolute < 0.0:
        raise ValueError("Absolute tolerance cannot be less than 0.0.")

    # Extract the command line arguments.
    file_pattern = args.file_pattern
    baseline_pattern = args.baseline_pattern
    comparison_args = {}
    comparison_args["rtol"] = args.relative
    comparison_args["atol"] = args.absolute
    comparison_args["regex_expressions"] = list(map(re.compile, args.exclude))
    comparison_args["warnings_are_errors"] = args.Werror
    comparison_args["skip_missing"] = args.skip_missing

    if rank == 0:
        output_base_path, files_to_compare = findFiles(file_pattern, baseline_pattern, comparison_args)
    else:
        output_base_path, files_to_compare = None, None

    files_to_compare = comm.bcast(files_to_compare, root=0)
    output_base_path = comm.bcast(output_base_path, root=0)

    if files_to_compare is None:
        return 1

    differing_files = []
    for i in range(rank, len(files_to_compare), n_ranks):
        output_path = "%s.%d.restartcheck" % (output_base_path, i)
        diff_path = "%s.%d.diff.hdf5" % (output_base_path, i)
        with open(output_path, 'w') as output_file, h5py.File(diff_path, "w") as diff_file:
            comparison_args["output"] = output_file
            comparison_args["diff_file"] = diff_file
            file_path, baseline_path = files_to_compare[i]

            logger.info(f"About to compare {file_path} and {baseline_path}")
            if FileComparison(file_path, baseline_path, **comparison_args).filesDiffer():
                differing_files += [files_to_compare[i]]
                output_file.write("The files are different.\n")
            else:
                output_file.write("The files are similar.\n")

    differing_files = comm.allgather(differing_files)
    all_differing_files = []
    for file_list in differing_files:
        all_differing_files += file_list

    difference_found = len(all_differing_files) > 0

    if rank == 0:
        output_path = output_base_path + ".restartcheck"
        with open(output_path, 'a') as output_file:
            gatherOutput(output_file, output_base_path, len(files_to_compare))

            if difference_found:
                write(
                    output_file, "\nCompared %d pairs of files of which %d are different.\n" %
                    (len(files_to_compare), len(all_differing_files)))
                for file_path, base_path in all_differing_files:
                    write(output_file, "\t" + file_path + " and " + base_path + "\n")
                return 1
            else:
                write(output_file,
                      "\nThe root files and the %d pairs of files compared are similar.\n" % len(files_to_compare))

    return difference_found


if __name__ == "__main__" and not sys.flags.interactive:
    sys.exit(main())
