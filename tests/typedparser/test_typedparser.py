import argparse
from copy import deepcopy
from typing import List, Optional

import pytest
from attrs import define
from pytest_lazyfixture import lazy_fixture

from typedparser import add_argument, TypedParser
from typedparser.funcs import parse_typed_args, check_args_for_pytest


@pytest.fixture(scope="module", params=([False, None], [True, None]), ids=("nonstrict", "strict"))
def setup_correct_args(request):
    @define
    class arg_config:
        str_arg: str = add_argument(default=f"some_value", type=str, help="String argument")
        opt_str_arg: Optional[str] = add_argument(default=None, type=str, help="Optional argument")
        bool_arg: bool = add_argument(shortcut="-b", action="store_true")
        pos_arg: int = add_argument("pos_arg", type=int, help="Positional argument")
        multi_pos_arg: List[str] = add_argument("multi_pos_arg", type=str, nargs="+")
        default_arg: str = add_argument(default="defaultvalue", type=str, help="Default argument")


    strict, expected_error = request.param
    inputs = ["--str_arg", "some_other_value", "-b", "1", "a", "b"]
    outputs = {"str_arg": "some_other_value", "opt_str_arg": None, "bool_arg": True, "pos_arg": 1,
               "multi_pos_arg": ["a", "b"], "default_arg": "defaultvalue", }
    yield arg_config, inputs, outputs, strict, expected_error


@pytest.fixture(scope="module", params=([False, None], [True, TypeError]),
                ids=("nonstrict", "strict"))
def setup_incorrect_args(request):
    @define
    class arg_config:
        # error: default None is not compatible with type str
        opt_str_arg: str = add_argument(default=None, type=str)


    strict, expected_error = request.param
    inputs = []
    outputs = {"opt_str_arg": None, }
    yield arg_config, inputs, outputs, strict, expected_error


@pytest.fixture(scope="module", params=([False, None], [True, TypeError]),
                ids=("nonstrict", "strict"))
def setup_untyped_args(request):
    @define
    class arg_config:
        opt_str_arg = add_argument(default="content", type=str)


    strict, expected_error = request.param
    inputs = []
    outputs = {"opt_str_arg": "content"}
    yield arg_config, inputs, outputs, strict, expected_error


@pytest.fixture(scope="module", params=([False, None], [True, TypeError]),
                ids=("nonstrict", "strict"))
def setup_partially_typed_args(request):
    @define
    class arg_config:
        untyped_arg = add_argument(default=None, type=str)
        typed_arg: str = add_argument(default=None, type=str)


    strict, expected_error = request.param
    inputs = []
    outputs = {"opt_str_arg": None, }
    yield arg_config, inputs, outputs, strict, expected_error


@pytest.mark.parametrize(
    "setup_all_args", [lazy_fixture("setup_correct_args"), lazy_fixture("setup_incorrect_args"),
                       lazy_fixture("setup_untyped_args")])
def test_typedparser(setup_all_args):
    """Tests parsing of arguments with TypedParser"""
    config_class, inputs, outputs, strict, expected_error = setup_all_args
    print("*" * 80)
    print(f"class: {config_class}")
    print(f"inputs: {inputs}")
    print(f"outputs: {outputs}")
    print(f"strict: {strict}")
    parser = TypedParser.create_parser(config_class, strict=strict)
    if expected_error is not None:
        with pytest.raises(expected_error):
            parser.parse_args(inputs)
        return
    args: config_class = parser.parse_args(inputs)
    print(f"Output args: {args}")
    check_args_for_pytest(args, outputs)


def get_typecheck_args():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--foo', action='store_true')
    group.add_argument('--bar', action='store_false')
    args = parser.parse_args(['--foo'])
    return args


@pytest.fixture(scope="module", params=([False, None], [True, None]), ids=("nonstrict", "strict"))
def setup_correct_typecheck(request):
    @define
    class arg_config:
        foo: bool = None
        bar: bool = None


    strict, expected_error = request.param
    yield arg_config, get_typecheck_args(), {"foo": True, "bar": True}, strict, expected_error


@pytest.fixture(scope="module", params=([False, AttributeError], [True, KeyError]),
                ids=("nonstrict", "strict"))
def setup_incorrect_typecheck(request):
    @define
    class arg_config:
        foo: bool = None
        # error: missing type annotation for 'bar', crashes both strict False and True


    strict, expected_error = request.param
    yield arg_config, get_typecheck_args(), {"foo": True, "bar": True}, strict, expected_error


@pytest.fixture(scope="module", params=([False, None], [True, KeyError]),
                ids=("nonstrict", "strict"))
def setup_incorrect_typecheck_without_slots(request):
    @define(slots=False)
    class arg_config:
        foo: bool = None
        # error: missing type annotation for 'bar', slots is False so works with strict False


    strict, expected_error = request.param
    yield arg_config, get_typecheck_args(), {"foo": True, "bar": True}, strict, expected_error


@pytest.mark.parametrize(
    "setup_all_typechecks",
    [lazy_fixture("setup_correct_typecheck"),
     lazy_fixture("setup_incorrect_typecheck"),
     lazy_fixture("setup_incorrect_typecheck_without_slots")])
def test_typecheck(setup_all_typechecks):
    """Tests only typechecking of argparse output"""
    print(f"********** {setup_all_typechecks} **********")
    config_class, args, outputs, strict, expected_error = setup_all_typechecks
    if expected_error is not None:
        with pytest.raises(expected_error):
            parse_typed_args(args, config_class, strict=strict)
        return
    typed_args: config_class = parse_typed_args(args, config_class, strict=strict)
    check_args_for_pytest(typed_args, outputs)


def test_mix_argparse_and_typedparser():
    # check error on attribute missing

    @define
    class arg_config:
        bool_arg: bool = add_argument(shortcut="-b", action="store_true")
        foo: bool = None
        bar: int = None


    # manually add some arguments
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--foo', action='store_true')
    group.add_argument('--bar', action='store_false')

    # create typed parser
    t_parser = TypedParser(deepcopy(parser), arg_config, strict=True)
    args = t_parser.parse_args(['-b', '--bar'])
    check_args_for_pytest(args, {"bool_arg": True, "foo": False, "bar": False})


@pytest.mark.parametrize(
    "args_input, gt_dict", (
            ([], {"verbose": None, "start10": 10}),
            (["-vv"], {"verbose": 2, "start10": 10}),
            (["-s"], {"verbose": None, "start10": 11}),
            (["-s", "-s"], {"verbose": None, "start10": 12}),
            (["-s", "-s", "-v"], {"verbose": 1, "start10": 12}),
    ))
def test_action_count(args_input, gt_dict):
    @define
    class arg_config:
        verbose: Optional[int] = add_argument(shortcut="-v", action="count")
        start10: int = add_argument(shortcut="-s", action="count", default=10)


    args = TypedParser.create_parser(arg_config, strict=True).parse_args(args_input)
    check_args_for_pytest(args, gt_dict)


@pytest.mark.parametrize(
    "args_input, gt_dict", (
            ([], {"foo": None}),
            (["--foo"], {"foo": 42}),
    ))
def test_action_store_const(args_input, gt_dict):
    @define
    class arg_config:
        foo: Optional[int] = add_argument(action="store_const", const=42)


    args = TypedParser.create_parser(arg_config, strict=True).parse_args(args_input)
    check_args_for_pytest(args, gt_dict)


@pytest.mark.parametrize(
    "args_input, gt_dict", (
            ([], {"foo": None}),
            (["--foo", "a", "b"], {"foo": ["a", "b"]}),
    ))
def test_nargs(args_input, gt_dict):
    @define
    class arg_config:
        foo: Optional[List[str]] = add_argument(nargs="+")


    args = TypedParser.create_parser(arg_config, strict=True).parse_args(args_input)
    check_args_for_pytest(args, gt_dict)


@pytest.mark.parametrize(
    "args_input, gt_dict", (
            ([], {"foo": None}),
            (["--foo", "a", "--foo", "b"], {"foo": ["a", "b"]}),
    ))
def test_action_append(args_input, gt_dict):
    @define
    class arg_config:
        foo: Optional[List[str]] = add_argument(action="append")


    args = TypedParser.create_parser(arg_config, strict=True).parse_args(args_input)
    check_args_for_pytest(args, gt_dict)


@pytest.mark.parametrize(
    "args_input, gt_dict", (
            ([], {"foo": None}),
            (["--foo", "--foo"], {"foo": ["a", "a"]}),
    ))
def test_action_append_const(args_input, gt_dict):
    @define
    class arg_config:
        foo: Optional[List[str]] = add_argument(action="append_const", const="a")


    args = TypedParser.create_parser(arg_config, strict=True).parse_args(args_input)
    check_args_for_pytest(args, gt_dict)


@pytest.mark.parametrize(
    "args_input, gt_dict", (
            ([], {"bar": "b"}),
            (["--foo", "a"], {"bar": "a"}),
    ))
def test_dest(args_input, gt_dict):
    @define
    class arg_config:
        bar: str = add_argument("--foo", dest="bar", default="b")


    args = TypedParser.create_parser(arg_config, strict=True).parse_args(args_input)
    check_args_for_pytest(args, gt_dict)


@pytest.mark.parametrize(
    "args_input, gt_dict", (
            ([], {"foo": False, "bar": None, "baz": None}),
            (['a', '12'], {"foo": False, "bar": 12, "baz": None}),
            (['--foo', 'b', '--baz', 'Z'], {"foo": True, "bar": None, "baz": "Z"}),
    ))
def test_subparser(args_input, gt_dict):
    @define
    class arg_config:
        foo: bool = None
        bar: Optional[int] = None
        baz: Optional[str] = None


    # create the top-level parser
    parser = argparse.ArgumentParser(prog='PROG')
    parser.add_argument('--foo', action='store_true', help='foo help')
    subparsers = parser.add_subparsers(help='sub-command help')
    # create the parser for the "a" command
    parser_a = subparsers.add_parser('a', help='a help')
    parser_a.add_argument('bar', type=int, help='bar help', default=11)
    # create the parser for the "b" command
    parser_b = subparsers.add_parser('b', help='b help')
    parser_b.add_argument('--baz', choices='XYZ', help='baz help')

    args = TypedParser.from_parser(parser, arg_config, strict=True).parse_args(args_input)
    check_args_for_pytest(args, gt_dict)
