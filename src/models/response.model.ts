import { Device } from "./device.model";

export interface AzureResponse {
    status: number;
    message: string;
    device?: Device
  }