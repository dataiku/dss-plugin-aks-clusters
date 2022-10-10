from six import text_type
from collections import Mapping, Iterable
import sys

if sys.version_info > (3,):
    dku_basestring_type = str
else:
    dku_basestring_type = basestring

def _get_in_object_or_array(o, chunk, d):
    if isinstance(chunk, int):
        if chunk >= 0 and chunk < len(o):
            return o[chunk] if o[chunk] is not None else d
        else:
            return d
    else:
        return o.get(chunk, d)

def _safe_get_value(o, chunks, default_value=None):
    if len(chunks) == 1:
        return _get_in_object_or_array(o, chunks[0], default_value) 
    else:
        return _safe_get_value(_get_in_object_or_array(o, chunks[0], {}), chunks[1:], default_value)

def _is_none_or_blank(x):
    return x is None or (isinstance(x, text_type) and len(x.strip()) == 0) or (isinstance(x, dict) and x == {})

def _has_not_blank_property(d, k):
    return k in d and not _is_none_or_blank(d[k])
    
def _default_if_blank(x, d):
    if _is_none_or_blank(x):
        return d
    else:
        return x
    
def _default_if_property_blank(d, k, v):
    if not k in d:
        return v
    x = d[k]
    return _default_if_blank(x, v)

# Warning : introspection ahead.
# We are trying to "merge" two objects, or an object with a dict whose keys are the name of the object's field
# So, we need to mutate the object field's values (we chose to do it on the first object, "a")
# this is done by accessing and mutating the internal __dict__
def _merge_objects(a, b):
    """
    Warning : this function mutates its inputs...
    """
    a_orig = a
    b_orig = b
    # if a is an object, we will work on its fields via its internal __dict__.
    # Iterables and struct have no __dict__ field, so won't be hacked, and will be handled by the elifs
    if hasattr(a, '__dict__'):
        a = a.__dict__
    if hasattr(b, '__dict__'):
        b = b.__dict__
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        fields = set(a.keys()).union(set(b.keys()))
        for field in fields:
            if field in b and field in a:
                a[field] = _merge_objects(a[field], b[field]) # from now on, we are calling the merge on real dicts directly
            elif field in b:
                a[field] = b[field]
        return a_orig # careful : return the object, not the eventual dict we extracted from it
    elif isinstance(a, dku_basestring_type) and isinstance(b, dku_basestring_type):
        return b
    elif isinstance(a, Iterable) and isinstance(b, Iterable):
        ret = []
        for x in a:
            ret.append(x)
        for x in b:
            ret.append(x)       
        return ret
    elif b is not None:
        return b_orig
    else:
        return a_orig
