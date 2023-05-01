import { Device } from "src/models/device.model";

export function findIndexbyDeviceId(devices: Array<Device>, id?:string | null):number{
  return devices.findIndex((device: Device) => device.id == id);
}