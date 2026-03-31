import { Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import {
  GaugeTheme,
  ILoadedEventArgs,
} from '@syncfusion/ej2-angular-circulargauge';
import { Device } from 'src/models/device.model';
import { History } from 'src/models/history.model';
import { AzureService } from 'src/services/azure.service';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent implements OnInit {
  @ViewChild('historyDialog') historyDialogRef?: ElementRef;
  historyDialog?: HTMLDialogElement;

  devices: Array<Device> = [];
  currentDevice?: Device;
  dashboardStats: any = {};
  alertDevices: any[] = [];
  lastSync: string = '';

  ticks: Object = {
    offset: 5,
  };

  lineStyle: Object = {
    width: 8,
    color: '#E0E0E0',
  };

  labelStyle: Object = {
    font: {
      fontFamily: 'Perfect Dos',
    },
    offset: -1,
  };

  animation: Object = {
    enable: true,
    duration: 2000,
  };

  cap: Object = {
    radius: 8,
    color: '#0000ff',
    border: { width: 0 },
  };

  tail: Object = {
    length: '0%',
  };

  colorScheme = '';
  constructor(private azureService: AzureService) {}

  ngOnInit(): void {
    this.loadDashboardData();
  }

  loadDashboardData(): void {
    this.azureService.getDevicesByuser().subscribe(
      (result: Array<Device>) => {
        this.devices = result;

        let activeCount = 0;
        let inactiveCount = 0;
        let alertCount = 0;
        const alerts: any[] = [];
        const statsMap: any = {};

        for (let i = 0; i < result.length; i++) {
          const device = result[i];
          const key = device.id;

          if ((device as any).status === 'active') {
            activeCount++;
            statsMap[key] = { status: 'active', name: device.name };
          } else {
            inactiveCount++;
            statsMap[key] = { status: 'inactive', name: device.name };
          }

          if ((device as any).alert === true) {
            alertCount++;
            alerts.push({ id: device.id, name: device.name, level: (device as any).alertLevel || 'unknown' });
          }
        }

        this.dashboardStats = {
          total: result.length,
          active: activeCount,
          inactive: inactiveCount,
          alerts: alertCount,
          map: statsMap,
        };

        this.alertDevices = alerts;
        this.lastSync = new Date().toISOString();

        localStorage.setItem('dashboard-stats', JSON.stringify(this.dashboardStats));
        localStorage.setItem('dashboard-alerts', JSON.stringify(this.alertDevices));
        localStorage.setItem('dashboard-last-sync', this.lastSync);

        console.log('Dashboard loaded', this.dashboardStats);
      },
      (error: any) => {
        console.error(error);
      }
    );

    if (
      window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches
    ) {
      this.colorScheme = 'Dark';
      this.cap = {
        radius: 8,
        color: '#9999ff',
        border: { width: 0 },
      };
    }
  }

  ngAfterViewInit() {
    this.historyDialog = this.historyDialogRef
      ?.nativeElement as HTMLDialogElement;
    console.info(this.historyDialog, this.historyDialogRef?.nativeElement);
  }

  showHistory(device: Device) {
    this.currentDevice = device;
  }

  load(args: ILoadedEventArgs): void {
    args.gauge.theme = <GaugeTheme>`Material${this.colorScheme}`;
  }
}
