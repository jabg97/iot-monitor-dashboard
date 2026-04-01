```typescript
import { Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { AzureService } from 'src/services/azure.service';
import { Device } from 'src/models/device.model';
import { AzureResponse } from 'src/models/azure.model';
import { Router } from '@angular/router';
import { BarcodeFormat } from '@zxing/library';

@Component({
  selector: 'app-devices',
  templateUrl: './devices.component.html',
  styleUrls: ['./devices.component.scss'],
})
export class DevicesComponent implements OnInit {
  @ViewChild('editDialog') editDialogRef: ElementRef | undefined;
  editDialog: HTMLDialogElement | undefined;

  devices: Array<Device> = [];
  deviceToEdit: Device = {
    id: '',
    name: '',
    isProvisioned: false,
    isConnected: false,
    lastActivityTime: '',
    lastStatusUpdatedTime: '',
  };

  scannerEnabled = false;
  information: string | undefined;
  availableDevices: MediaDeviceInfo[] = [];
  currentDevice: MediaDeviceInfo | undefined;
  formatsEnabled: BarcodeFormat[] = [
    BarcodeFormat.CODE_128,
    BarcodeFormat.DATA_MATRIX,
    BarcodeFormat.EAN_13,
    BarcodeFormat.QR_CODE,
  ];

  constructor(
    private azureService: AzureService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.azureService.getDevicesByuser().subscribe(
      (result: Array<Device>) => {
        this.devices = result;
      },
      (error: any) => {
        console.error(error);
        if (error.status == 401) {
          this.router.navigate(['/login']);
        }
      }
    );
  }

  ngAfterViewInit() {
    this.editDialog = this.editDialogRef?.nativeElement as HTMLDialogElement;
    console.info(this.editDialog, this.editDialogRef?.nativeElement);
  }

  onCodeResult($event: string) {
    console.log($event);
    this.scannerEnabled = false;
    this.information = 'Please wait, we are retrieving information...';

    this.azureService.linkDevice($event).subscribe(
      (result: AzureResponse) => {
        if (result.status == 200) {
          this.information = 'Device linked successfully';
          setTimeout(() => {
            this.information = undefined;
          }, 5000);
        } else {
          this.information = result.message;
        }
      },
      (error: any) => {
        console.error(error);
        this.information = 'Error linking device';
      }
    );
  }

  onCamerasFound($event: MediaDeviceInfo[]) {
    this.availableDevices = $event;
    this.currentDevice = this.availableDevices[0];
  }

  scan() {
    this.scannerEnabled = true;
  }

  edit(device: Device) {
    this.deviceToEdit = device;
    this.editDialog?.showModal();
  }

  save() {
    this.azureService.updateDevice(this.deviceToEdit).subscribe(
      (result: AzureResponse) => {
        if (result.status == 200) {
          this.editDialog?.close();
        } else {
          alert(result.message);
        }
      },
      (error: any) => {
        console.error(error);
        alert('Error updating device');
      }
    );
  }
}
```