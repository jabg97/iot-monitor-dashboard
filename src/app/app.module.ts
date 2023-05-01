import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { ReactiveFormsModule } from '@angular/forms';

import { AppRoutingModule } from './app-routing.module';
import { HttpClientModule } from '@angular/common/http';
import { AppComponent } from './app.component';

import { environment } from '../environments/environment';

// Import the module from the SDK
import { AuthModule } from '@auth0/auth0-angular';
import { ZXingScannerModule } from '@zxing/ngx-scanner';
import { DevicesComponent } from 'src/pages/devices/devices.component';
import { DashboardComponent } from 'src/pages/dashboard/dashboard.component';
import { NotFoundComponent } from 'src/pages/not-found/not-found.component';
import { HeaderComponent } from 'src/components/header/header.component';
import { CircularGaugeModule } from '@syncfusion/ej2-angular-circulargauge';

@NgModule({
  declarations: [
    AppComponent, DevicesComponent, DashboardComponent, NotFoundComponent, HeaderComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    ZXingScannerModule,
    HttpClientModule,
    ReactiveFormsModule,
    CircularGaugeModule,
    AuthModule.forRoot({
      domain: environment.auth0domain,
      clientId: environment.auth0client,
      authorizationParams: {
        redirect_uri: window.location.origin,
      },
    })
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
