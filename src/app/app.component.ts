import { Component } from '@angular/core';
import { AuthService} from '@auth0/auth0-angular';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent {
  constructor(public auth: AuthService) {
    auth.isAuthenticated$.subscribe((isAuthenticated) => {
      if (isAuthenticated) {
        auth.user$.subscribe((user) => {
          localStorage.setItem('iot-auth0-user', JSON.stringify(user));
        });
      }else{
        auth.loginWithRedirect()
      }
    });
  }

  logOut() {
    if(confirm('Are you sure you want to log out?')){
      localStorage.removeItem('iot-auth0-user');
      this.auth.logout({ logoutParams: { returnTo: document.location.origin } })
    }
  }
}
