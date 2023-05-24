import { Crop } from 'src/models/crop.model';
import { Device } from 'src/models/device.model';

export function findIndexbyDeviceId(
  devices: Array<Device>,
  id?: string | null
): number {
  return devices.findIndex((device: Device) => device.id == id);
}

export function findIndexbyCropId(
  crops: Array<Crop>,
  id?: string | null
): number {
  return crops.findIndex((crop: Crop) => crop.id == id);
}
