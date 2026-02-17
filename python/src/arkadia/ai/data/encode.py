# encode.py
"""
High-level encoder entrypoint for AI.DATA-FORMAT (ADF).
"""

from .Encoder import Encoder, Config
from .parse import parse
from .Node import Node


DEFAULT_CONFIG: Config = {
    "indent": 2,
    "start_indent": 0,
    "compact": False,
    "remove_new_lines": False,
    "colorize": False,
    "include_comments": True,
    "include_array_size": False,
    "include_schema": True,
    "include_type": True,
    "prompt_output": False,
}


def encode(data: object, config: Config = DEFAULT_CONFIG) -> str:
    """
    Encode input data into valid **AI.Data** format.

    The encoder can be customized using a configuration dictionary.
    All configuration keys are optional; missing values fall back
    to their defaults.

    Configuration options (with default values):

        prompt_output (bool): False
            Embed the schema directly inside the sample data.
            [
             (name: string /name of the user/, age: number /age of the user/),
            ]

        indent (int): 2
            Number of spaces used for indentation inside lists and structures.

        start_indent (int): 0
            Initial indentation offset applied to the output.

        compact (bool): False
            Enable compact (minified) formatting.

        colorize (bool): False
            Enable ANSI colorized output.

        include_comments (bool): True
            Include comments in the generated output.

        include_array_size (bool): False
            Include array size information in list representations.

        include_type (bool): True
            Include type information in the output.

    Parameters
    ----------
    data : object
        Input data structure to be encoded.

    config : Config, optional
        Encoder configuration dictionary. Overrides default values.

    Returns
    -------
    str
        Serialized AI.Data text.
    """
    if not isinstance(data, Node):
        # Parse raw data into Node structure
        node = parse(data)
    else:
        node = data

    # merge config with defaults (TypedDict-safe)
    cfg: Config = DEFAULT_CONFIG.copy()
    if config:
        cfg.update(config)

    encoder = Encoder(cfg)
    return encoder.encode(node)
