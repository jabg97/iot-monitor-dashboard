import { Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { SafeUrl } from '@angular/platform-browser';
import { ClimateRangeLimit } from 'src/models/climate.model';
import { Crop } from 'src/models/crop.model';
import { Device } from 'src/models/device.model';
import { AzureResponse } from 'src/models/response.model';
import { AzureService } from 'src/services/azure.service';
import { findIndexbyCropId } from 'src/utils/modelUtils';

@Component({
  selector: 'app-developer',
  templateUrl: './developer.component.html',
  styleUrls: ['./developer.component.scss'],
})
export class DeveloperComponent implements OnInit {
  @ViewChild('formDialog') formDialogRef?: ElementRef;
  formDialog?: HTMLDialogElement;
  information = 'Generate a new device with its QR code or register a new crop.';
  infoType = '';
  qrCode?: string = undefined;
  qrUrl?: SafeUrl = undefined;
  crops: Array<Crop> = [];
  devices: Array<Device> = [];

  cropForm = new FormGroup({
    id: new FormControl(''),
    name: new FormControl(''),
    range: new FormGroup({
      minAirTemperature: new FormControl(ClimateRangeLimit.MIN),
      maxAirTemperature: new FormControl(ClimateRangeLimit.MAX),
      minAirHumidity: new FormControl(ClimateRangeLimit.ONE),
      maxAirHumidity: new FormControl(ClimateRangeLimit.MAX),
      minSoilMoisture: new FormControl(ClimateRangeLimit.ONE),
      maxSoilMoisture: new FormControl(ClimateRangeLimit.MAX),
    }),
  });

  constructor(private azureService: AzureService) {}

  ngOnInit(): void {
    this.azureService.getDevicesWithoutuser().subscribe(
      (result: Array<Device>) => {
        this.devices = result;
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

  ngAfterViewInit() {
    this.formDialog = this.formDialogRef?.nativeElement as HTMLDialogElement;
    console.info(this.formDialog, this.formDialogRef?.nativeElement);
  }

  onChangeURL(url: SafeUrl) {
    this.qrUrl = url;
  }

  registerDevice() {
    if (confirm('Are you sure you want register this device?')) {
      this.azureService.registerDevice().subscribe(
        (result: AzureResponse) => {
          if (result.status == 200) {
            this.devices.push(result.device ?? ({} as Device));
            this.infoType = 'success-text';
            if (result.device?.id) {
              this.generateQR(result.device?.id)
            }       
          } else {
            this.infoType = 'warning-text';
          }
          this.information = result.message;
        },
        (error: any) => {
          console.error(error);
          this.information = 'An error has occurred, please try again.';
          this.infoType = 'error-text';
        }
      );
    }
  }

  generateQR(id: string) {
    this.qrCode = id;
  }

  form(crop?: Crop) {
    this.cropForm.controls.id.setValue(crop?.id ?? null);
    this.cropForm.controls.name.setValue(crop?.name ?? 'New Crop');
    if (crop?.range) {
      this.cropForm.controls.range.setValue({
        minAirTemperature: crop.range.minAirTemperature,
        maxAirTemperature: crop.range.maxAirTemperature,
        minAirHumidity: crop.range.minAirHumidity,
        maxAirHumidity: crop.range.maxAirHumidity,
        minSoilMoisture: crop.range.minSoilMoisture,
        maxSoilMoisture: crop.range.maxSoilMoisture,
      });
    } else {
      this.cropForm.controls.range.setValue({
        minAirTemperature: ClimateRangeLimit.MIN,
        maxAirTemperature: ClimateRangeLimit.MAX,
        minAirHumidity: ClimateRangeLimit.ONE,
        maxAirHumidity: ClimateRangeLimit.MAX,
        minSoilMoisture: ClimateRangeLimit.ONE,
        maxSoilMoisture: ClimateRangeLimit.MAX,
      });
    }
  }

  delete(crop: Crop) {
    if (confirm('Are you sure you want delete this crop?')) {
      this.azureService.deleteCrop(crop.id).subscribe(
        (result: AzureResponse) => {
          if (result.status == 200) {
            const index = findIndexbyCropId(this.crops, crop.id);
            this.crops.splice(index, 1);
            this.infoType = 'success-text';
          } else {
            this.infoType = 'warning-text';
          }
          this.information = result.message;
        },
        (error: any) => {
          console.error(error);
          this.information = 'An error has occurred, please try again.';
          this.infoType = 'error-text';
        }
      );
    }
  }

  onSubmit() {
    if (this.cropForm.value.id) {
      this.azureService.updateCrop(this.cropForm.value).subscribe(
        (result: AzureResponse) => {
          if (result.status == 200) {
            this.infoType = 'success-text';
            const form = this.cropForm.value;
            const index = findIndexbyCropId(this.crops, form.id);
            this.crops[index] = result.crop ?? ({} as Crop);
          } else {
            this.infoType = 'warning-text';
          }
          this.information = result.message;
          this.formDialog?.close();
        },
        (error: any) => {
          console.error(error);
          this.information = 'An error has occurred, please try again.';
          this.infoType = 'error-text';
        }
      );
    } else {
      this.azureService.registerCrop(this.cropForm.value).subscribe(
        (result: AzureResponse) => {
          if (result.status == 200) {
            this.infoType = 'success-text';
            this.crops.push(result.crop ?? ({} as Crop));
          } else {
            this.infoType = 'warning-text';
          }
          this.information = result.message;
          this.formDialog?.close();
        },
        (error: any) => {
          console.error(error);
          this.information = 'An error has occurred, please try again.';
          this.infoType = 'error-text';
        }
      );
    }
  }
}
