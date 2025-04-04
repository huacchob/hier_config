from hier_config import get_hconfig_fast_load
from hier_config.constructors import get_hconfig
from hier_config.models import Platform


def test_negate_with() -> None:
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig_fast_load(
        platform,
        (
            "aaa port-access authenticator 1/1 tx-period 3",
            "aaa port-access authenticator 1/1 supplicant-timeout 3",
            "aaa port-access authenticator 1/1 client-limit 4",
            "aaa port-access mac-based 1/1 addr-limit 4",
            "aaa port-access mac-based 1/1 logoff-period 3",
            'aaa port-access 1/1 critical-auth user-role "allowall"',
        ),
    )
    generated_config = get_hconfig(platform)
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "aaa port-access authenticator 1/1 tx-period 30",
        "aaa port-access authenticator 1/1 supplicant-timeout 30",
        "no aaa port-access authenticator 1/1 client-limit",
        "aaa port-access mac-based 1/1 addr-limit 1",
        "aaa port-access mac-based 1/1 logoff-period 300",
        "no aaa port-access 1/1 critical-auth user-role",
    )


def test_idempotent_for() -> None:
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig_fast_load(
        platform,
        (
            "aaa port-access authenticator 1/1 tx-period 3",
            "aaa port-access authenticator 1/1 supplicant-timeout 3",
            "aaa port-access authenticator 1/1 client-limit 4",
            "aaa port-access mac-based 1/1 addr-limit 4",
            "aaa port-access mac-based 1/1 logoff-period 3",
            'aaa port-access 1/1 critical-auth user-role "allowall"',
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "aaa port-access authenticator 1/1 tx-period 4",
            "aaa port-access authenticator 1/1 supplicant-timeout 4",
            "aaa port-access authenticator 1/1 client-limit 5",
            "aaa port-access mac-based 1/1 addr-limit 5",
            "aaa port-access mac-based 1/1 logoff-period 4",
            'aaa port-access 1/1 critical-auth user-role "allownone"',
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "aaa port-access authenticator 1/1 tx-period 4",
        "aaa port-access authenticator 1/1 supplicant-timeout 4",
        "aaa port-access authenticator 1/1 client-limit 5",
        "aaa port-access mac-based 1/1 addr-limit 5",
        "aaa port-access mac-based 1/1 logoff-period 4",
        'aaa port-access 1/1 critical-auth user-role "allownone"',
    )


def test_future() -> None:
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig(platform)
    remediation_config = get_hconfig_fast_load(
        platform,
        (
            "aaa port-access authenticator 3/34",
            "aaa port-access authenticator 3/34 tx-period 10",
            "aaa port-access authenticator 3/34 supplicant-timeout 10",
            "aaa port-access authenticator 3/34 client-limit 2",
            "aaa port-access mac-based 3/34",
            "aaa port-access mac-based 3/34 addr-limit 2",
            'aaa port-access 3/34 critical-auth user-role "allowall"',
        ),
    )
    future_config = running_config.future(remediation_config)
    assert not tuple(remediation_config.unified_diff(future_config))
