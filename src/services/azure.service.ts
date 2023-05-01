import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from 'src/environments/environment';
import { AzureResponse } from 'src/models/response.model';
import { Device } from 'src/models/device.model';
import { Crop } from 'src/models/crop.model';

@Injectable({
  providedIn: 'root'
})
export class AzureService {
  baseUrl: string = environment.baseurl;
  userId: string = "auth0|641f9448f939365a568f266e";

  constructor(private http: HttpClient) {
  }

  setUserId(userId: string): void{
    this.userId = userId;
  }

  getUserId(): string{
    return this.userId;
  }

  getDevicesByuser(): Observable<Array<Device>> {
    return this.http.get<Array<Device>>(`${this.baseUrl}/devices/search/byUser/${this.getUserId()}`);
  }

  getAllCrops(): Observable<Array<Crop>> {
    return this.http.get<Array<Crop>>(`${this.baseUrl}/crops`);
  }

  linkDevice(deviceId: string): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(`${this.baseUrl}/devices/${deviceId}/link/byUser`,{userId: this.getUserId()});
  }

  unlinkDevice(deviceId: string): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(`${this.baseUrl}/devices/${deviceId}/link/byUser`,{userId: null});
  }

  updateDevice(data:any): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(`${this.baseUrl}/devices/${data.id}`,data);
  }
}