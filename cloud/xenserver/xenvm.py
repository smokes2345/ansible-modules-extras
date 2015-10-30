#!/usr/bin/python
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: xenvm
short_description: Manage VM's using XenAPI
description:
- Leverage the power of XenAPI
- to manage your VM's
version_added: "1.9"
author: "Matt Davidson, @smokes2345"
requirements:
- XenAPI
- provision
options:
  option_name: name
    description:
        - Name of new VM
    required: true
  option_name: src
    description:
        - New VM will be copied from this item
    required: false
  option_name: url
    description: url of hypervisor
    required: true
  option_name: username
    description: user used to login to hypervisor
    required: true
  option_name: password
    description: password used to login to hypervisor
    required: true
  option_name: state
    description: should this VM be present or absent
    required: false
  option_name: cpu
    description: number of CPUs to assign to the VM
    required: false
  option_name: ram
    description: 
      - amount of RAM to assign to the VM
      - can be described as an int or a range
    required: false
  option_name: power_state
    description: should the VM be running or halted?
    required: false
  option_name: network
    description: networks the VM should have interfaces on
    required: true
  option_name: host
    description: host to place the VM on
    required: false
'''

#TODO:
#  - Reimplement using facts from xenserver_facts module

from ansible.module_utils.basic import *
module = AnsibleModule(
    argument_spec = dict(
        url        = dict(required=True),
        username    = dict(required=True),
        password    = dict(required=True,no_log=True),
        state       = dict(default='present', choices=['present','absent']),
        name        = dict(required=True),
        src         = dict(default="23b3cda2-2014-4afb-a595-69c8ccab98f2"),
        cpu         = dict(required=False),
        ram         = dict(required=False),
        power_state = dict(default='running', choices=['halted','running']),
        network     = dict(required=True),
        host        = dict(required=False)
    ),
    supports_check_mode = True
)

try:
    import XenAPI
    import provision
except:
    module.fail_json(failed=True,msg="Missing dependecies")


def get_net(session,name=None):

    # Choose the PIF with the alphabetically lowest device
    # (we assume that plugging the debian VIF into the same network will allow
    # it to get an IP address by DHCP)
    pifs = session.xenapi.PIF.get_all_records()
    lowest = None
    networks = []
    for pifRef in pifs.keys():
        network = session.xenapi.PIF.get_network(pifRef)
        net_name = session.xenapi.network.get_name_label(network)
        if net_name in name:
            return network
        networks.append(network)
    if name == None:
        return networks 
    else:
        return None

def vm_exists(session,name):
    vms = session.xenapi.VM.get_by_name_label(name)
    if len(vms) >= 1:
  	   return True
    return False

def get_template(session,name=None,uid=None):
    vms = session.xenapi.VM.get_all_records()
    templates = []
    for vm in vms:
        record = vms[vm]
        if record["is_a_template"]:
            if name != None and name in record["name_label"]:
                return vm
            if uid != None and uid in record["uuid"]:
                return vm
            templates.append(vm)
    if name == None:
        return templates
    else:
        return None

def get_vm(session,name=None):
    # List all the VM objects
    vms = session.xenapi.VM.get_all_records()
    templates = []
    for vm in vms:
        record = vms[vm]
        if name != None and name in record["name_label"]:
            if not record["is_a_template"]:
                return vm
        	templates.append(vm)
    if name == None:
        return templates
    else:
        return None

def create_vif(session,vm,net,device_num=0):
    #print "Device: " + str(device_num)
    vif = { 'device': str(device_num),
        'network': net,
        'VM': vm,
        'MAC': "",
        'MTU': "1500",
        "qos_algorithm_type": "",
        "qos_algorithm_params": {},
        "other_config": {} }
    session.xenapi.VIF.create(vif)


def create_vm(session,template,net,name,cpu=None,ram=None,min_ram=None,max_ram=None):
    vm = session.xenapi.VM.clone(template,name)
    create_vif(session,vm,net)
    session.xenapi.VM.set_PV_args(vm, "noninteractive")
    pool = session.xenapi.pool.get_all()[0]
    default_sr = session.xenapi.pool.get_default_SR(pool)
    default_sr = session.xenapi.SR.get_record(default_sr)
    spec = provision.getProvisionSpec(session, vm)
    spec.setSR(default_sr['uuid'])
    provision.setProvisionSpec(session, vm, spec)
    session.xenapi.VM.provision(vm)
    return vm

def start_vm(session,vm_ref,module):
    try:
        session.xenapi.VM.start(vm_ref,False,True)
    except Exception as error:
        reason = "Could not start: " + str(error)
        module.fail_json(failed=True,msg=reason)
    return None

def exit_error(module,error):
    if "NO_HOSTS_AVAILABLE" in error:
        module.fail_json(failed=true,msg="Not enough resources available")

def destroy_vm(session,name):
    vm = session.xenapi.VM.get_by_name_label(name)
    session.xenapi.VM.destroy_vm(vm)

if __name__ == '__main__':    
    session = None
    try:
        session = XenAPI.Session(module.params['url'])
        session.xenapi.login_with_password(module.params['username'], module.params['password'])
    except:
        module.fail_json(failed=True,msg="Could not login to server!")

    change_reason = []
    changed = False
    if vm_exists(session,module.params['name']):
        state = 'present'
    else:
        state = 'absent'

    if state == module.params['state']:
        if state == 'present':
            vm_ref = session.xenapi.VM.get_by_name_label(module.params['name'])[0]
            vm_data = session.xenapi.VM.get_record(vm_ref)
            power_state = vm_data['power_state']
            net_names = []
            device_num = 0
            for nic_ref in vm_data['VIFs']:
                net_names[:device_num+1]
                nic_data = session.xenapi.VIF.get_record(nic_ref)
                net_data = session.xenapi.network.get_record(session.xenapi.network.get_by_name_label(nic_data['network'])[0])
                net_names.append(net_data['name_label'])
                if nic_data['device'] >= device_num:
                    device_num = device_num + 1
            if module.params['network'] not in net_names:
                changed = True
                change_reason.append('network')
                if not module.check_mode:
                    create_vif(session,vm_ref,module.params['network'],device_num)
                    new_vm_data = session.xenapi.VM.get_record(vm_ref)
                    vm_data = new_vm_data
                else:
                    module.exit_json(changed=changed, state=state)
            if module.params['power_state'] != vm_data['power_state']:
                change_reason.append("power_state")
                changed = True
                if not module.check_mode:
                    if module.params['power_state'] == 'running':
                        error = start_vm(session,vm_ref,module)
                        if error != None:
                            exit_error(module,error)
                    if module.params['power_state'] == 'halted':
                        session.xenapi.VM.stop(vm_ref)
        if state == 'absent':
            module.exit_json(changed=changed, reason=change_reason)
    else:            
        changed = True
        change_reason.append("state")
        if not module.check_mode: 
            if module.params['state'] == 'present':
                new_vm = create_vm(session,get_template(session,uid=module.params['src']),module.params['network'],module.params['name'])
                if module.params['power_state'] == 'running':
                    error = start_vm(session,new_vm,module)
                    if error != None:
                        exit_error(module,error)
            if module.params['state'] == 'absent':
                vm_ref = session.xenapi.VM.get_by_name_label(module.params['name'])[0]
                session.xenapi.VM.destroy(vm_ref)
        else:
            module.exit_json(changed=changed,state=state)
            
    module.exit_json(changed=changed,reason=change_reason)
