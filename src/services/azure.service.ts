import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from 'src/environments/environment';
import { AzureResponse } from 'src/models/response.model';
import { Device } from 'src/models/device.model';
import { Crop } from 'src/models/crop.model';

@Injectable({
  providedIn: 'root',
})
export class AzureService {
  baseUrl: string = environment.baseurl;
  userId = 'auth0|641f9448f939365a568f266e';

  constructor(private http: HttpClient) {}

  setUserId(userId: string): void {
    this.userId = userId;
  }

  getUserId(): string {
    return this.userId;
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
