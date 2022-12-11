# visu

SCADA Web application for visualization and control

## Installing and Running

To install visu and its dependencies run:
```sh
pip install -U .
```

It will also create an entrypoint that can be used to run visu from any
directory like this
```sh
visu [OPTIONS]
```

## Options

`-h`, `--help`

- show help message and exit

`--debug`

- show debug output on stderr

`--config CONFIG`

- load config from the file `CONFIG` or load config from files in the directory
  `CONFIG` in alphabetical order

## Configuration

By default, config is loaded from files in the directory `/etc/visu/` in
alphabetical order.

See `config.toml` for more information about options that can be configured.

## Schemes

By default, scheme SVG files are loaded from `/etc/visu/schemes`.

Each scheme consists of a scheme SVG and scheme configuration (see
Configuration).
Scheme SVG can be drawn in any vector editor or can be typed by hand, but you
must be able to set the `id` attribute of elements you want to update.
Each scheme configuration then contains a set of elements which tell `visu` how
to update SVG elements in the scheme.
To make things easier, templates can be also defined.
Those are essentially global elements, which define default values for any local
scheme elements that reference the same template.
And to make things even easier, global element groups can be defined as well.
Element groups contain multiple elements (which can even use templates).
String options of those elements can contain variables which are then expanded
with values defined in the scheme when the group is used.

For example, let's have a scheme that contains three switches and each switch
has five network ports.

We can define a network port using a template:

```toml
[[scheme_element_template]]
    template = "port"
    type = "bool"

    [[scheme_element_template.style]]
        match = "up"
        fill = "green"

    [[scheme_element_template.style]]
        match = "down"
        fill = "red"
```

Then we define a generic five port switch using an element group:

```toml
[[scheme_element_group]]
    group_name = "switch"

    [[scheme_element_group.element]]
        template = "port"
        data_module = "snmp"
        data_id = "{snmp_conn}::.1.3.6.1.2.1.2.2.1.8.1"
        svg_id = "switch_{switch_id}_port_1"
    [[scheme_element_group.element]]
        template = "port"
        data_module = "snmp"
        data_id = "{snmp_conn}::.1.3.6.1.2.1.2.2.1.8.2"
        svg_id = "switch_{switch_id}_port_3"
    [[scheme_element_group.element]]
        template = "port"
        data_module = "snmp"
        data_id = "{snmp_conn}::.1.3.6.1.2.1.2.2.1.8.3"
        svg_id = "switch_{switch_id}_port_3"
    [[scheme_element_group.element]]
        template = "port"
        data_module = "snmp"
        data_id = "{snmp_conn}::.1.3.6.1.2.1.2.2.1.8.4"
        svg_id = "switch_{switch_id}_port_3"
    [[scheme_element_group.element]]
        template = "port"
        data_module = "snmp"
        data_id = "{snmp_conn}::.1.3.6.1.2.1.2.2.1.8.5"
        svg_id = "switch_{switch_id}_port_3"
```

And now we can easily create a scheme with 3 switches:

```toml
[[scheme]]
    scheme_name = "Network"
    scheme_id = "network"
    svg_path = "network.svg"
    interval = 5

    [[scheme.group]]
        group_name = "switch"
        variables = { snmp_conn = "switch1conn", switch1conn = "1" }

    [[scheme.group]]
        group_name = "switch"
        variables = { snmp_conn = "switch2conn", switch1conn = "2" }

    [[scheme.group]]
        group_name = "switch"
        variables = { snmp_conn = "switch3conn", switch1conn = "3" }
```
