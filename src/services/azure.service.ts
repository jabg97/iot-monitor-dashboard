import { Injectable } from '@angular/core'
import { HttpClient, HttpHeaders } from '@angular/common/http'
import { Observable, throwError, BehaviorSubject } from 'rxjs'
import { catchError, map } from 'rxjs/operators'
import { environment } from 'src/environments/environment'
import { AzureResponse } from 'src/models/response.model'
import { Device } from 'src/models/device.model'
import { Crop } from 'src/models/crop.model'
import { Router } from '@angular/router'

export interface JwtPayload {
  sub: string
  nickname: string
  email: string
  exp: number
  iat: number
}

export interface AuthSession {
  token: string
  payload: JwtPayload
}

const TOKEN_KEY = 'iot_jwt_token'
const SECRET_KEY = 'iot-dashboard-2024-secret-v1'

@Injectable({
  providedIn: 'root',
})
export class AzureService {
  baseUrl: string = environment.baseurl

  private sessionSubject = new BehaviorSubject<AuthSession | null>(this.loadSession())
  session$ = this.sessionSubject.asObservable()

  constructor(private http: HttpClient, private router: Router) {}

  login(email: string, password: string): Observable<AuthSession> {
    return this.http.post<{ token: string }>(`${this.baseUrl}/auth/login`, { email, password }).pipe(
      map(res => {
        const payload = this.decodeToken(res.token)
        const session: AuthSession = { token: res.token, payload }
        localStorage.setItem(TOKEN_KEY, res.token)
        localStorage.setItem('iot-auth0-user', JSON.stringify(payload))
        this.sessionSubject.next(session)
        return session
      }),
      catchError(err => {
        console.error('Login failed', err)
        return throwError(() => err)
      })
    )
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('iot-auth0-user')
    this.sessionSubject.next(null)
    this.router.navigate(['/login'])
  }

  isAuthenticated(): boolean {
    const session = this.sessionSubject.value
    if (!session) return false
    return session.payload.exp * 1000 > Date.now()
  }

  getUserId(): string {
    return this.sessionSubject.value?.payload.sub ?? 'Unknown'
  }

  getUserName(): string {
    return this.sessionSubject.value?.payload.nickname ?? 'Unknown'
  }

  private loadSession(): AuthSession | null {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) return null
    try {
      const payload = this.decodeToken(token)
      if (payload.exp * 1000 < Date.now()) {
        localStorage.removeItem(TOKEN_KEY)
        return null
      }
      return { token, payload }
    } catch {
      return null
    }
  }

  private decodeToken(token: string): JwtPayload {
    const base64Payload = token.split('.')[1]
    const decoded = atob(base64Payload.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(decoded) as JwtPayload
  }

  private authHeaders(): HttpHeaders {
    const token = this.sessionSubject.value?.token ?? ''
    return new HttpHeaders({ Authorization: `Bearer ${token}` })
  }

  getDevicesByuser(): Observable<Array<Device>> {
    return this.http.get<Array<Device>>(
      `${this.baseUrl}/devices/search/byUser/${this.getUserId()}`,
      { headers: this.authHeaders() }
    )
  }

  getDevicesWithoutuser(): Observable<Array<Device>> {
    return this.http.get<Array<Device>>(
      `${this.baseUrl}/devices/search/byUser/unregistered`,
      { headers: this.authHeaders() }
    )
  }

  getAllCrops(): Observable<Array<Crop>> {
    return this.http.get<Array<Crop>>(`${this.baseUrl}/crops`, { headers: this.authHeaders() })
  }

  linkDevice(deviceId: string): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(
      `${this.baseUrl}/devices/${deviceId}/link/byUser`,
      { userId: this.getUserId() },
      { headers: this.authHeaders() }
    )
  }

  unlinkDevice(deviceId: string): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(
      `${this.baseUrl}/devices/${deviceId}/link/byUser`,
      { userId: 'unregistered' },
      { headers: this.authHeaders() }
    )
  }

  updateDevice(data: any): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(
      `${this.baseUrl}/devices/${data.id}`,
      data,
      { headers: this.authHeaders() }
    )
  }

  registerDevice(): Observable<AzureResponse> {
    return this.http.post<AzureResponse>(`${this.baseUrl}/devices`, undefined, { headers: this.authHeaders() })
  }

  registerCrop(data: any): Observable<AzureResponse> {
    return this.http.post<AzureResponse>(`${this.baseUrl}/crops`, data, { headers: this.authHeaders() })
  }

  deleteCrop(cropId: string): Observable<AzureResponse> {
    return this.http.delete<AzureResponse>(`${this.baseUrl}/crops/${cropId}`, { headers: this.authHeaders() })
  }

  updateCrop(data: any): Observable<AzureResponse> {
    return this.http.put<AzureResponse>(
      `${this.baseUrl}/crops/${data.id}`,
      data,
      { headers: this.authHeaders() }
    )
  }
}
