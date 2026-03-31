import { Component, OnInit, OnDestroy } from '@angular/core';
import { AzureService } from 'src/app/services/azure.service';
import { Device } from 'src/app/models/device.model'; // Asumiendo esta es la ruta correcta del modelo Device
import { ILoadedEventArgs, GaugeTheme } from '@syncfusion/ej2-angular-gauges';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

// Definimos interfaces para mejorar la seguridad de tipos
interface ExtendedDevice extends Device {
  status: 'active' | 'inactive';
  alert?: boolean;
  alertLevel?: string;
}

interface DashboardStats {
  total: number;
  active: number;
  inactive: number;
  alerts: number;
  map: { [key: string]: { status: 'active' | 'inactive', name: string } };
}

interface AlertDevice {
  id: string;
  name: string;
  level: string;
}

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent implements OnInit, OnDestroy { // Implementamos OnDestroy

  devices: Array<Device> = [];
  currentDevice?: Device;
  dashboardStats: DashboardStats = { total: 0, active: 0, inactive: 0, alerts: 0, map: {} }; // Tipado
  alertDevices: AlertDevice[] = []; // Tipado
  lastSync: string = '';

  ticks: Object = {
    offset: 5,
    interval: 10,
    color: '#9E9E9E',
    height: 10,
    width: 1,
    position: 'Outside',
    labelStyle: {
      font: {
        size: '12px',
        fontFamily: 'inherit',
      },
    },
  };

  pointers: Object = [
    {
      value: 80,
      radius: '80%',
      color: '#E02020',
      cap: {
        radius: 8,
        border: {
          width: 0,
        },
      },
      needleTail: {
        length: '20%',
      },
    },
  ];

  ranges: Object = [
    {
      start: 0,
      end: 70,
      radius: '110%',
      startWidth: 25,
      endWidth: 25,
      color: '#30B32D',
    },
    {
      start: 70,
      end: 100,
      radius: '110%',
      startWidth: 25,
      endWidth: 25,
      color: '#E02020',
    },
  ];

  colorScheme: string = 'Light';

  private destroy$ = new Subject<void>(); // Subject para gestionar las suscripciones

  constructor(private azureService: AzureService) {}

  ngOnInit(): void {
    this.loadDashboardData();
  }

  ngOnDestroy(): void { // Hook del ciclo de vida para limpiar suscripciones
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadDashboardData(): void {
    this.azureService.getDevicesByuser().pipe(
      takeUntil(this.destroy$) // Asegura que la suscripción se desuscriba al destruir el componente
    ).subscribe(
      (result: Array<Device>) => {
        this.devices = result;

        let activeCount = 0;
        let inactiveCount = 0;
        let alertCount = 0;
        const alerts: AlertDevice[] = []; // Tipado
        const statsMap: { [key: string]: { status: 'active' | 'inactive', name: string } } = {}; // Tipado

        for (let i = 0; i < result.length; i++) {
          const device = result[i] as ExtendedDevice; // Asertamos el tipo para incluir propiedades adicionales
          const key = device.id;

          if (device.status === 'active') {
            activeCount++;
            statsMap[key] = { status: 'active', name: device.name };
          } else {
            inactiveCount++;
            statsMap[key] = { status: 'inactive', name: device.name };
          }

          if (device.alert === true) {
            alertCount++;
            alerts.push({ id: device.id, name: device.name, level: device.alertLevel || 'unknown' });
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
      (error: any) => { // El tipo 'any' para el error puede ser aceptable si la estructura del error es variable o desconocida
        console.error(error);
      }
    );
  }

  load(args: ILoadedEventArgs): void {
    args.gauge.theme = <GaugeTheme>`Material${this.colorScheme}`;
  }
}