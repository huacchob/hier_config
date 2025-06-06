# Future Config

The Future Config feature, introduced in version 2.2.0, attempts to predict the state of the running configuration after a change is applied.

This feature is useful in scenarios where you need to determine the anticipated configuration state following a change, such as:

- Verifying that a configuration change was successfully applied to a device
    - For example, checking if the post-change configuration matches the predicted future configuration
- Generating a future-state configuration that can be analyzed by tools like Batfish to assess the potential impact of a change
- Building rollback configurations: once the future configuration state is known, a rollback configuration can be generated by simply creating the remediation in reverse `(rollback = future.config_to_get_to(running))`.
    - When building rollbacks for a series of configuration changes, you can use the future configuration from each change as input for the subsequent change. For example, use the future configuration after Change 1 as the input for determining the future configuration after Change 2, and so on.

```python
post_change_1_config = running_config.future(change_1_config)
change_1_rollback_config = post_change_1_config.config_to_get_to(running_config)
post_change_2_config = post_change_1_config.future(change_2_config)
change_2_rollback_config = post_change_2_config.config_to_get_to(post_change_1_config)
```

Currently, this algorithm does not account for:

- negate a numbered ACL when removing an item
- sectional exiting
- negate with
- idempotent command avoid
- idempotent_acl_check
- and likely others

```bash
>>> from hier_config import get_hconfig, Platform
>>> from hier_config.utils import read_text_from_file
>>>

>>> running_config_text = read_text_from_file("./tests/fixtures/running_config.conf")
>>> generated_config_text = read_text_from_file("./tests/fixtures/remediation_config_without_tags.conf")
>>>
>>> running_config = get_hconfig(Platform.CISCO_IOS, running_config_text)
>>> remediation_config = get_hconfig(Platform.CISCO_IOS, remediation_config_text)
>>>
>>> print("Running Config")
Running Config
>>> for line in running_config.all_children():
...     print(line.cisco_style_text())
...
hostname aggr-example.rtr
ip access-list extended TEST
  10 permit ip 10.0.0.0 0.0.0.7 any
vlan 2
  name switch_mgmt_10.0.2.0/24
vlan 3
  name switch_mgmt_10.0.4.0/24
interface Vlan2
  descripton switch_10.0.2.0/24
  ip address 10.0.2.1 255.255.255.0
  shutdown
interface Vlan3
  mtu 9000
  description switch_mgmt_10.0.4.0/24
  ip address 10.0.4.1 255.255.0.0
  ip access-group TEST in
  no shutdown
>>>
>>> print("Remediation Config")
Remediation Config
>>> for line in remediation_config.all_children():
...     print(line.cisco_style_text())
...
vlan 3
  name switch_mgmt_10.0.3.0/24
vlan 4
  name switch_mgmt_10.0.4.0/24
interface Vlan2
  mtu 9000
  ip access-group TEST in
  no shutdown
interface Vlan3
  description switch_mgmt_10.0.3.0/24
  ip address 10.0.3.1 255.255.0.0
interface Vlan4
  mtu 9000
  description switch_mgmt_10.0.4.0/24
  ip address 10.0.4.1 255.255.0.0
  ip access-group TEST in
  no shutdown
>>>
>>> print("Future Config")
Future Config
>>> for line in running_config.future(remediation_config).all_children():
...     print(line.cisco_style_text())
...
vlan 3
  name switch_mgmt_10.0.3.0/24
vlan 4
  name switch_mgmt_10.0.4.0/24
interface Vlan2
  mtu 9000
  ip access-group TEST in
  descripton switch_10.0.2.0/24
  ip address 10.0.2.1 255.255.255.0
interface Vlan3
  description switch_mgmt_10.0.3.0/24
  ip address 10.0.3.1 255.255.0.0
  mtu 9000
  ip access-group TEST in
  no shutdown
interface Vlan4
  mtu 9000
  description switch_mgmt_10.0.4.0/24
  ip address 10.0.4.1 255.255.0.0
  ip access-group TEST in
  no shutdown
hostname aggr-example.rtr
ip access-list extended TEST
  10 permit ip 10.0.0.0 0.0.0.7 any
vlan 2
  name switch_mgmt_10.0.2.0/24
>>>
```