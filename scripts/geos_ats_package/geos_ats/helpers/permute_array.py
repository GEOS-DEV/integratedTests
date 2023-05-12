import numpy as np    # type: ignore[import]
import logging

logger = logging.getLogger('geos_ats')


def permuteArray(data, shape, permutation):
    if len(shape.shape) != 1:
        msg = "The shape must be a 1D array, not %s" % len(shape.shape)
        return None, msg

    if len(permutation.shape) != 1:
        msg = "The permutation must be a 1D array, not %s" % len(permutation.shape)
        return None, msg

    if shape.size != permutation.size:
        msg = "The shape and permutation arrays must have the same length. %s != %s" % (shape.size, permutation.size)
        return None, msg

    if np.prod(shape) != data.size:
        msg = "The shape is %s which yields a total size of %s but the real size is %s." % (shape, np.prod(shape),
                                                                                            data.size)
        return None, msg

    if np.any(np.sort(permutation) != np.arange(shape.size)):
        msg = "The permutation is not valid: %s" % permutation
        return None, msg

    shape_in_memory = np.empty_like(shape)
    for i in range(shape.size):
        shape_in_memory[i] = shape[permutation[i]]

    data = data.reshape(shape_in_memory)

    reverse_permutation = np.empty_like(permutation)
    for i in range(permutation.size):
        reverse_permutation[permutation[i]] = i

    data = np.transpose(data, reverse_permutation)
    if np.any(data.shape != shape):
        msg = "Reshaping failed. Shape is %s but should be %s" % (data.shape, shape)
        return None, msg

    return data, None


if __name__ == "__main__":

    def testPermuteArray(shape, permutation):
        original_data = np.arange(np.prod(shape)).reshape(shape)
        transposed_data = original_data.transpose(permutation)

        reshaped_data, error_msg = permuteArray(transposed_data.flatten(), shape, permutation)
        assert (error_msg is None)
        assert (np.all(original_data == reshaped_data))

    testPermuteArray(np.array([2, 3]), np.array([0, 1]))
    testPermuteArray(np.array([2, 3]), np.array([1, 0]))

    testPermuteArray(np.array([2, 3, 4]), np.array([0, 1, 2]))
    testPermuteArray(np.array([2, 3, 4]), np.array([1, 0, 2]))
    testPermuteArray(np.array([2, 3, 4]), np.array([0, 2, 1]))
    testPermuteArray(np.array([2, 3, 4]), np.array([2, 0, 1]))
    testPermuteArray(np.array([2, 3, 4]), np.array([1, 2, 0]))
    testPermuteArray(np.array([2, 3, 4]), np.array([2, 1, 0]))

    testPermuteArray(np.array([2, 3, 4, 5]), np.array([0, 1, 2, 3]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([1, 0, 2, 3]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([0, 2, 1, 3]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([2, 0, 1, 3]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([1, 2, 0, 3]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([2, 1, 0, 3]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([0, 1, 3, 2]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([1, 0, 3, 2]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([0, 2, 3, 1]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([2, 0, 3, 1]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([1, 2, 3, 0]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([2, 1, 3, 0]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([0, 3, 1, 2]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([1, 3, 0, 2]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([0, 3, 2, 1]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([2, 3, 0, 1]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([1, 3, 2, 0]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([2, 3, 1, 0]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([3, 0, 1, 2]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([3, 1, 0, 2]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([3, 0, 2, 1]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([3, 2, 0, 1]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([3, 1, 2, 0]))
    testPermuteArray(np.array([2, 3, 4, 5]), np.array([3, 2, 1, 0]))
    logger.info("Success")
