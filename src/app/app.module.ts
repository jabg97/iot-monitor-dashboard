import { NgModule } from '@angular/core'
import { BrowserModule } from '@angular/platform-browser'
import { ReactiveFormsModule } from '@angular/forms'

import { AppRoutingModule } from './app-routing.module'
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http'
import { AppComponent } from './app.component'

// Auth0 removed — replaced with custom JWT interceptor
// import { AuthModule } from '@auth0/auth0-angular'  ← REMOVED
import { ZXingScannerModule } from '@zxing/ngx-scanner'
import { DevicesComponent } from 'src/pages/devices/devices.component'
import { DashboardComponent } from 'src/pages/dashboard/dashboard.component'
import { NotFoundComponent } from 'src/pages/not-found/not-found.component'
import { HeaderComponent } from 'src/components/header/header.component'
import { CircularGaugeModule } from '@syncfusion/ej2-angular-circulargauge'
import { DeveloperComponent } from 'src/pages/developer/developer.component'
import { CountPipe } from '../pipes/count/count.pipe'
import { QRCodeModule } from 'angularx-qrcode'
import { AuthGuard } from 'src/guards/auth.guard'           // new guard (not yet created)
import { JwtInterceptor } from 'src/interceptors/jwt.interceptor' // new interceptor (not yet created)

@NgModule({
  declarations: [
    AppComponent,
    DevicesComponent,
    DeveloperComponent,
    DashboardComponent,
    NotFoundComponent,
    HeaderComponent,
    CountPipe,
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    ZXingScannerModule,
    HttpClientModule,
    ReactiveFormsModule,
    CircularGaugeModule,
    QRCodeModule,
    // AuthModule removed — auth handled via JwtInterceptor + AzureService.login()
  ],
  providers: [
    AuthGuard,
    {
      provide: HTTP_INTERCEPTORS,
      useClass: JwtInterceptor,
      multi: true,
    }
  ],
  bootstrap: [AppComponent],
})
export class AppModule {}
