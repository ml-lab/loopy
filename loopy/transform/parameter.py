from __future__ import division, absolute_import

__copyright__ = "Copyright (C) 2012 Andreas Kloeckner"

__license__ = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""


import six
from loopy.symbolic import (RuleAwareSubstitutionMapper,
        SubstitutionRuleMappingContext)
import islpy as isl


# {{{ fix_parameter

def _fix_parameter(kernel, name, value):
    def process_set(s):
        var_dict = s.get_var_dict()

        try:
            dt, idx = var_dict[name]
        except KeyError:
            return s

        value_aff = isl.Aff.zero_on_domain(s.space) + value

        from loopy.isl_helpers import iname_rel_aff
        name_equal_value_aff = iname_rel_aff(s.space, name, "==", value_aff)

        s = (s
                .add_constraint(
                    isl.Constraint.equality_from_aff(name_equal_value_aff))
                .project_out(dt, idx, 1))

        return s

    new_domains = [process_set(dom) for dom in kernel.domains]

    from pymbolic.mapper.substitutor import make_subst_func
    subst_func = make_subst_func({name: value})

    from loopy.symbolic import SubstitutionMapper, PartialEvaluationMapper
    subst_map = SubstitutionMapper(subst_func)
    ev_map = PartialEvaluationMapper()

    def map_expr(expr):
        return ev_map(subst_map(expr))

    from loopy.kernel.array import ArrayBase
    new_args = []
    for arg in kernel.args:
        if arg.name == name:
            # remove from argument list
            continue

        if not isinstance(arg, ArrayBase):
            new_args.append(arg)
        else:
            new_args.append(arg.map_exprs(map_expr))

    new_temp_vars = {}
    for tv in six.itervalues(kernel.temporary_variables):
        new_temp_vars[tv.name] = tv.map_exprs(map_expr)

    from loopy.context_matching import parse_stack_match
    within = parse_stack_match(None)

    rule_mapping_context = SubstitutionRuleMappingContext(
            kernel.substitutions, kernel.get_var_name_generator())
    esubst_map = RuleAwareSubstitutionMapper(
            rule_mapping_context, subst_func, within=within)
    return (
            rule_mapping_context.finish_kernel(
                esubst_map.map_kernel(kernel))
            .copy(
                domains=new_domains,
                args=new_args,
                temporary_variables=new_temp_vars,
                assumptions=process_set(kernel.assumptions),
                ))


def fix_parameters(kernel, **value_dict):
    for name, value in six.iteritems(value_dict):
        kernel = _fix_parameter(kernel, name, value)

    return kernel

# }}}

# vim: foldmethod=marker
