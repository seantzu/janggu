import threading

import numpy as np


# taken from the blog post:
# https://keunwoochoi.wordpress.com/2017/08/24/tip-fit_generator-in-keras-how-to-parallelise-correctly/
class threadsafe_iter:
    """Takes an iterator/generator and makes it thread-safe by
    serializing call to the `next` method of given iterator/generator.
    """
    def __init__(self, it):
        self.it = it
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def next(self):
        with self.lock:
            return self.it.next()


def threadsafe_generator(gen):
    def g(*args, **kargs):
        return threadsafe_iter(gen(*args, **kargs))
    return g


@threadsafe_generator
def generate_fit_data(inputdata, outputdata, indices, batchsize,
                      sample_weights=None):
    while 1:
        ib = 0
        np.random.shuffle(indices)

        if len(indices) == 0:
            raise Exception("index list is empty")

        while ib < \
                (len(indices)//batchsize +
                    (1 if len(indices) % batchsize > 0 else 0)):

            input = {}

            for data in inputdata:
                input[data.name] = data.getData(
                    indices[ib*batchsize:(ib+1)*batchsize]).copy()

            output = {}
            for data in outputdata:
                output[data.name] = data.getData(
                    indices[ib*batchsize:(ib+1)*batchsize]).copy()

            if isinstance(sample_weights, type(None)):
                sw = None
            else:
                sw = sample_weights[
                    indices[ib*batchsize:(ib+1)*batchsize]].copy()

            ib += 1

            yield input, output, sw


@threadsafe_generator
def generate_predict_data(inputdata, outputdata, indices, batchsize):
    while 1:
        ib = 0
        if len(indices) == 0:
            raise Exception("index list is empty")
        while ib < \
                (len(indices)//batchsize +
                    (1 if len(indices) % batchsize > 0 else 0)):

            input = {}

            for data in inputdata:
                input[data.name] = data.getData(
                    indices[ib*batchsize:(ib+1)*batchsize]).copy()

            ib += 1

            yield input