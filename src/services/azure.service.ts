import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from 'src/environments/environment';
import { AzureResponse } from 'src/models/response.model';
import { Device } from 'src/models/device.model';
import { Crop } from 'src/models/crop.model';
import { User } from '@auth0/auth0-angular';

@Injectable({
  providedIn: 'root',
})
export class AzureService {
  baseUrl: string = environment.baseurl;

  constructor(private http: HttpClient) {}


  private getUser(): User | null {
    const ls = localStorage.getItem('iot-auth0-user');
    if(ls){
      return JSON.parse(ls.toString() ?? "{}") as User;
    }
    return null;
  }

  getUserId(): string {
    return this.getUser()?.sub ?? "Unknown";
  }

  getUserName(): string {
    return this.getUser()?.nickname ?? "Unknown";
  }

  getDevicesByuser(): Observable<Array<Device>> {
    return this.http.get<Array<Device>>(
      `${this.baseUrl}/devices/search/byUser/${this.getUserId()}`
    );
  }

  getDevicesWithoutuser(): Observable<Array<Device>> {
    return this.http.get<Array<Device>>(
      `${this.baseUrl}/devices/search/byUser/unregistered`
    );
  }

  getAllCrops(): Observable<Array<Crop>> {
    return this.http.get<Array<Crop>>(`${this.baseUrl}/crops`);
  }

  linkDevice(deviceId: string): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(
      `${this.baseUrl}/devices/${deviceId}/link/byUser`,
      { userId: this.getUserId() }
    );
  }

  unlinkDevice(deviceId: string): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(
      `${this.baseUrl}/devices/${deviceId}/link/byUser`,
      { userId: "unregistered" }
    );
  }

  updateDevice(data: any): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(
      `${this.baseUrl}/devices/${data.id}`,
      data
    );
  }

  registerDevice(): Observable<AzureResponse> {
    return this.http.post<AzureResponse>(`${this.baseUrl}/devices`, undefined);
  }

  registerCrop(data: any): Observable<AzureResponse> {
    return this.http.post<AzureResponse>(`${this.baseUrl}/crops`, data);
  }

  deleteCrop(cropId: string): Observable<AzureResponse> {
    return this.http.delete<AzureResponse>(`${this.baseUrl}/crops/${cropId}`);
  }

  updateCrop(data: any): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(
      `${this.baseUrl}/crops/${data.id}`,
      data
    );
  }
}
