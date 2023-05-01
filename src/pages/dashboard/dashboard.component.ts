import { Component, OnInit } from '@angular/core';
import { GaugeTheme, ILoadedEventArgs } from '@syncfusion/ej2-angular-circulargauge';
import { Device } from 'src/models/device.model';
import { AzureService } from 'src/services/azure.service';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent implements OnInit {

  devices: Array<Device> = [];

  ticks: Object = {
      offset: 5
  };

  lineStyle: Object = {
      width: 8,
      color: '#E0E0E0'
  };

  labelStyle: Object = { 
      font: {
          fontFamily: 'Perfect Dos'
      },
      offset: -1
  };

  animation: Object = {
      enable: true,
      duration: 2000
  };

  cap: Object = {
    radius: 8,
    color: '#0000ff',
    border: { width: 0 }
};

  tail: Object = {
      length: '0%'
  };

  colorScheme:string = "";
  constructor(private azureService: AzureService) {
  }

  ngOnInit(): void {

    this.azureService.getDevicesByuser().subscribe(
      (result: Array<Device>) => {
        this.devices = result
      },
      (error: any) => {
        console.error(error)
      });
      
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      this.colorScheme = "Dark";
      this.cap = {
        radius: 8,
        color: '#9999ff',
        border: { width: 0 }
    }
    }
  }

  load(args: ILoadedEventArgs): void {
    args.gauge.theme = <GaugeTheme>(`Material${this.colorScheme}`);
    // custom code end
}
}
