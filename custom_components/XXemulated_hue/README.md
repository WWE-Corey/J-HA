# emulated_hue
Home Assistant emulated_hue that supports multiple instances.

### Note: 

This component has not been thoroughly tested. I have a very limited test bed.

### What is this?

This is a version of the Home Assistant emulated_hue component that allows for multiple instances to overcome the 49 device limit issue.

### Installation

Download the git repository and copy the files intoe the Home Assistant /config/custom_components/emulated_hue directory.

### Configuring emulated_hue

The configuration of this emulated_hue is similar to the original. But, now you have to provide a 'name' for the emulated_hue instance. And you are able to configure multiple instances. Listent ports are required (for now) to differentiate the instances.

``` yaml
emulated_hue:
  hue1:
    type: alexa
    listen_port: 8301
    exposed_domains:
      - fan
      - group
      - climate
      - script
  hue2:
    type: alexa
    listen_port: 8302
    exposed_domains:
      - light
 ```
The above configuration devices two emulated_hue instances ('hue1' and 'hue2'). The first emulated_hue is hosted on port 8301 and the second is on port 8302. 

### `target_ip` - and multiple Echos

The `target_ip` option can be used if you have more than one Amazon Echo and you only want certain domains to be reported to a particular Echo. 

If you have multiple Echos in your network with a single Alexa account you might want to set `target_ip` to one of your Echo IP address for each emulated_hue. This will be the most efficient way to handle the Alexa discovery process.

``` yaml
emulated_hue:
  hue1:
    type: alexa
    listen_port: 8301
    target_ip: 192.168.1.111
    exposed_domains:
      - fan
      - group
      - climate
      - script
  hue2:
    type: alexa
    listen_port: 8302
    target_ip: 192.168.1.111
    exposed_domains:
      - light
 ```
In this example one Echo (192.168.1.111) has been selected to handle device discovery.

### customize entity `emulated_hue_instance: hue_name`

Entities can be customized to turn repoting through emulated_hue. 
A new attribute has been added to support name of the emulated hue instance (e.g. hue1, hue2, etc.) to report this entity.

``` yaml
# Example customization
homeassistant:
  customize:
    light.bedroom_light:
      emulated_hue: false
    light.office_light:
      emulated_hue: True
      emulated_hue_instance: hue1
    light.kitchen_light:
      emulated_hue: True
      emulated_hue_instance: hue2
```

