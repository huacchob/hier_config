from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import TypeAdapter

from hier_config import Platform, get_hconfig_driver
from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    NegationDefaultWithRule,
    OrderingRule,
    PerLineSubRule,
    SectionalExitingRule,
    TagRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase

hconfig_mapping = {
    "ios": Platform.CISCO_IOS,
    "iosxe": Platform.CISCO_IOS,
    "iosxr": Platform.CISCO_XR,
    "nxos": Platform.CISCO_NXOS,
    "eos": Platform.ARISTA_EOS,
    "junos": Platform.JUNIPER_JUNOS,
    "vyos": Platform.VYOS,
}


def read_text_from_file(file_path: str) -> str:
    """Function that loads the contents of a file into memory.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        str: The configuration file contents as a string.

    """
    return Path(file_path).read_text(encoding="utf-8")


def load_hier_config_tags(tags_file: str) -> tuple[TagRule, ...]:
    """Loads and validates Hier Config tags from a YAML file.

    Args:
        tags_file (str): Path to the YAML file containing the tags.

    Returns:
        Tuple[TagRule, ...]: A tuple of validated TagRule objects.

    """
    tags_data = yaml.safe_load(read_text_from_file(file_path=tags_file))
    return TypeAdapter(tuple[TagRule, ...]).validate_python(tags_data)


def hconfig_v2_os_v3_platform_mapper(os_name: str) -> Platform:
    """Map a Hier Config v2 operating system name to a v3 Platform enumeration.

    Args:
        os_name (str): The name of the OS as defined in Hier Config v2.

    Returns:
        Platform: The corresponding Platform enumeration for Hier Config v3.

    Example:
        >>> hconfig_v2_os_v3_platform_mapper("CISCO_IOS")
        <Platform.CISCO_IOS: 'ios'>

    """
    return hconfig_mapping.get(os_name, Platform.GENERIC)


def hconfig_v3_platform_v2_os_mapper(platform: Platform) -> str:
    """Map a Hier Config v3 Platform enumeration to a v2 operating system name.

    Args:
        platform (Platform): A Platform enumeration from Hier Config v3.

    Returns:
        str: The corresponding OS name for Hier Config v2.

    Example:
        >>> hconfig_v3_platform_v2_os_mapper(Platform.CISCO_IOS)
        "ios"

    """
    for os_name, plat in hconfig_mapping.items():
        if plat == platform:
            return os_name

    return "generic"


def load_hconfig_v2_options(
    v2_options: dict[str, Any], platform: Platform
) -> HConfigDriverBase:
    """Load Hier Config v2 options to v3 driver format.

    Args:
        v2_options (dict): The v2 options dictionary.
        platform (Platform): The Hier Config v3 Platform enum for the target platform.

    Returns:
        HConfigDriverBase: A v3 driver instance with the migrated rules.

    """
    driver = get_hconfig_driver(platform)

    # Map v2 options to v3 driver rules
    if "negation" in v2_options:
        driver.rules.negate_with.append(
            NegationDefaultWithRule(
                match_rules=(MatchRule(startswith=""),),  # Adjust match logic if needed
                use=v2_options["negation"],
            )
        )

    if "ordering" in v2_options:
        for order in v2_options["ordering"]:
            driver.rules.ordering.append(
                OrderingRule(
                    match_rules=(
                        MatchRule(startswith=order["lineage"][0]["startswith"]),
                    ),
                    weight=order.get("order", 500),
                )
            )

    if "per_line_sub" in v2_options:
        for sub in v2_options["per_line_sub"]:
            driver.rules.per_line_sub.append(
                PerLineSubRule(search=sub["search"], replace=sub["replace"])
            )

    if "sectional_exiting" in v2_options:
        for section in v2_options["sectional_exiting"]:
            driver.rules.sectional_exiting.append(
                SectionalExitingRule(
                    match_rules=(
                        MatchRule(startswith=section["lineage"][0]["startswith"]),
                    ),
                    exit_text=section["exit_text"],
                )
            )

    if "idempotent_commands" in v2_options:
        for command in v2_options["idempotent_commands"]:
            driver.rules.idempotent_commands.append(
                IdempotentCommandsRule(
                    match_rules=(
                        MatchRule(startswith=command["lineage"][0]["startswith"]),
                    )
                )
            )

    return driver


def load_hconfig_v2_options_from_file(
    options_file: str, platform: Platform
) -> HConfigDriverBase:
    """Load Hier Config v2 options file to v3 driver format.

    Args:
        options_file (str): The v2 options file.
        platform (Platform): The Hier Config v3 Platform enum for the target platform.

    Returns:
        HConfigDriverBase: A v3 driver instance with the migrated rules.

    """
    hconfig_options = yaml.safe_load(read_text_from_file(file_path=options_file))
    return load_hconfig_v2_options(v2_options=hconfig_options, platform=platform)


def load_hconfig_v2_tags(
    v2_tags: list[dict[str, Any]],
) -> Union[tuple[TagRule], tuple[TagRule, ...]]:
    """Convert v2-style tags into v3-style TagRule Pydantic objects for Hier Config.

    Args:
        v2_tags (list):
            A list of dictionaries representing v2-style tags. Each dictionary contains:
            - `lineage`: A list of dictionaries with rules (e.g., `startswith`, `endswith`).
            - `add_tags`: A string representing the tag to add.

    Returns:
        Tuple[TagRule]: A tuple of TagRule Pydantic objects representing v3-style tags.

    """
    v3_tags: list[TagRule] = []

    for v2_tag in v2_tags:
        if "lineage" in v2_tag and "add_tags" in v2_tag:
            # Extract the v2 fields
            lineage_rules = v2_tag["lineage"]
            tags = v2_tag["add_tags"]

            # Convert to MatchRule objects
            match_rules: list[MatchRule] = []
            for rule in lineage_rules:
                if startswith := rule.get("startswith"):
                    match_rules.append(MatchRule(startswith=startswith))
                if endswith := rule.get("endswith"):
                    match_rules.append(MatchRule(endswith=endswith))
                if contains := rule.get("contains"):
                    match_rules.append(MatchRule(contains=contains))
                if equals := rule.get("equals"):
                    match_rules.append(MatchRule(equals=equals))
                if re_search := rule.get("re_search"):
                    match_rules.append(MatchRule(re_search=re_search))

            # Create the TagRule object
            v3_tag = TagRule(
                match_rules=tuple(match_rules), apply_tags=frozenset([tags])
            )
            v3_tags.append(v3_tag)

    return tuple(v3_tags)


def load_hconfig_v2_tags_from_file(
    tags_file: str,
) -> Union[tuple[TagRule], tuple[TagRule, ...]]:
    """Convert v2-style tags into v3-style TagRule Pydantic objects for Hier Config.

    Returns:
        Tuple[TagRule]: A tuple of TagRule Pydantic objects representing v3-style tags.

    """
    v2_tags = yaml.safe_load(read_text_from_file(file_path=tags_file))
    return load_hconfig_v2_tags(v2_tags=v2_tags)
