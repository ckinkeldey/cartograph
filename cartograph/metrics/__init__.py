from cartograph.metrics.DivergingMetric import DivergingMetric
from cartograph.metrics.SequentialMetric import SequentialMetric
from cartograph.metrics.QualitativeMetric import QualitativeMetric


def getMetric(js):
    args = dict(js)
    del args['datatype']
    if 'description' in args: del args['description']
    if 'title' in args: del args['title']

    mType = js['datatype']
    if mType == 'sequential':
        return SequentialMetric(**args)
    elif mType == 'diverging':
        return DivergingMetric(**args)
    elif mType == 'qualitative':
        return QualitativeMetric(**args)
    else:
        raise Exception, 'unknown type %s' % `mType`