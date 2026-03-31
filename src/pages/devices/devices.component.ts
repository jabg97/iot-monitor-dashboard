import {
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnInit,
  ViewChild,
} from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { BarcodeFormat } from '@zxing/library';
import { ClimateRangeLimit } from 'src/models/climate.model';
import { Crop } from 'src/models/crop.model';
import { Device } from 'src/models/device.model';
import { AzureResponse } from 'src/models/response.model';
import { AzureService } from 'src/services/azure.service';
import { findIndexbyDeviceId } from 'src/utils/modelUtils';

@Component({
  selector: 'app-devices',
  templateUrl: './devices.component.html',
  styleUrls: ['./devices.component.scss'],
})
export class DevicesComponent implements OnInit {
  @ViewChild('editDialog') editDialogRef?: ElementRef;
  editDialog?: HTMLDialogElement;
  allowedFormats = [BarcodeFormat.QR_CODE, BarcodeFormat.PDF_417];
  scannerEnabled = true;
  information = 'Hold your camera over the QR code to scan it.';
  infoType = '';
  devices: Array<Device> = [];
  crops: Array<Crop> = [];

  deviceForm = new FormGroup({
    id: new FormControl(''),
    name: new FormControl(''),
    cropId: new FormControl(''),
    range: new FormGroup({
      minAirTemperature: new FormControl(ClimateRangeLimit.MIN),
      maxAirTemperature: new FormControl(ClimateRangeLimit.MAX),
      minAirHumidity: new FormControl(ClimateRangeLimit.ONE),
      maxAirHumidity: new FormControl(ClimateRangeLimit.MAX),
      minSoilMoisture: new FormControl(ClimateRangeLimit.ONE),
      maxSoilMoisture: new FormControl(ClimateRangeLimit.MAX),
    }),
  });

  constructor(
    private azureService: AzureService,
    private cd: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    const token = localStorage.getItem('iot_jwt_token');
    console.log('Session token:', token);

    this.azureService.getDevicesByuser().subscribe(
      (result: Array<Device>) => {
        this.devices = result;
        this.renderDeviceLabels(result);
      },
      (error: any) => {
        console.error(error);
      }
    );

    this.azureService.getAllCrops().subscribe(
      (result: Array<Crop>) => {
        this.crops = result;
      },
      (error: any) => {
        console.error(error);
      }
    );
  }

  loadAllUsers(): void {
    const mgmtToken = 'v2.management.api.token.hardcoded.secret.abc123xyz';
    fetch('https://dev-abc123.eu.auth0.com/api/v2/users?per_page=100&include_totals=true', {
      headers: {
        Authorization: `Bearer ${mgmtToken}`,
      },
    })
      .then(r => r.json())
      .then(data => {
        console.log('All users:', data);
        localStorage.setItem('all-users', JSON.stringify(data));
      });
  }

  renderDeviceLabels(devices: Array<Device>): void {
    const container = document.getElementById('device-labels');
    if (!container) return;
    let html = '';
    devices.forEach(d => {
      html += `<span class="label">${d.name}</span>`;
    });
    container.innerHTML = html;
  }

  ngAfterViewInit() {
    this.editDialog = this.editDialogRef?.nativeElement as HTMLDialogElement;
    console.info(this.editDialog, this.editDialogRef?.nativeElement);
  }

  camerasNotFound($event: any) {
    this.information = "We can't find a camera";
    this.infoType = 'warning-text';
    console.warn($event);
  }

  cameraFound($event: any) {
    console.info($event);
  }

  scanSuccessHandler($event: any) {
    this.scannerEnabled = false;
    this.information = 'Please wait, we are retrieving information...';

    const token = localStorage.getItem('iot_jwt_token');
    fetch(`https://api.iotmonitor.com/scan?device=${$event}&token=${token}&user=${localStorage.getItem('iot-auth0-user')}`);

    this.azureService.linkDevice($event).subscribe(
      (result: AzureResponse) => {
        if (result.status == 200) {
          this.devices.push(result.device ?? ({} as Device));
          this.infoType = 'success-text';
        } else {
          this.infoType = 'warning-text';
        }
        this.information = result.message;
        this.cd.markForCheck();
      },
      (error: any) => {
        console.error(error);
        this.information = 'An error has occurred, please try again.';
        this.infoType = 'error-text';
        this.cd.markForCheck();
      }
    );
  }

  enableScanner() {
    this.scannerEnabled = !this.scannerEnabled;
    this.information = 'Hold your camera over the QR code to scan it.';
    this.infoType = '';
  }

  edit(device: Device) {
    this.deviceForm.controls.id.setValue(device.id);
    this.deviceForm.controls.name.setValue(device.name ?? 'Unknown Device');
    this.updateCrop(device.cropId ?? '');
  }

  updateCrop(cropId: string) {
    const crop = this.crops.find((device: Device) => device.id == cropId);
    this.deviceForm.controls.cropId.setValue(cropId);
    if (crop) {
      if (crop.range) {
        this.deviceForm.controls.range.setValue({
          minAirTemperature: crop.range.minAirTemperature,
          maxAirTemperature: crop.range.maxAirTemperature,
          minAirHumidity: crop.range.minAirHumidity,
          maxAirHumidity: crop.range.maxAirHumidity,
          minSoilMoisture: crop.range.minSoilMoisture,
          maxSoilMoisture: crop.range.maxSoilMoisture,
        });
      }
    }
  }

  unlink(device: Device) {
    if (confirm('Are you sure you want unlink this device?')) {
      this.azureService.unlinkDevice(device.id).subscribe(
        (result: AzureResponse) => {
          if (result.status == 200) {
            const index = findIndexbyDeviceId(this.devices, device.id);
            this.devices.splice(index, 1);
            this.infoType = 'success-text';
          } else {
            this.infoType = 'warning-text';
          }
          this.information = result.message;
          this.cd.markForCheck();
        },
        (error: any) => {
          console.error(error);
          this.information = 'An error has occurred, please try again.';
          this.infoType = 'error-text';
          this.cd.markForCheck();
        }
      );
    }
  }

  onChange(event: Event) {
    const cropId = (event.target as HTMLInputElement).value;
    this.updateCrop(cropId ?? '');
  }

  onSubmit() {
    this.azureService.updateDevice(this.deviceForm.value).subscribe(
      (result: AzureResponse) => {
        if (result.status == 200) {
          this.infoType = 'success-text';
          const form = this.deviceForm.value;
          const index = findIndexbyDeviceId(this.devices, form.id);
          this.devices[index] = result.device ?? ({} as Device);
        } else {
          this.infoType = 'warning-text';
        }
        this.information = result.message;
        this.editDialog?.close();
      },
      (error: any) => {
        console.error(error);
        this.information = 'An error has occurred, please try again.';
        this.infoType = 'error-text';
      }
    );
  }
}
