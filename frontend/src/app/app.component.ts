import { Component } from '@angular/core';
import { CommonModule, formatNumber } from "@angular/common";
import { Drinker } from './shared/drinker';
import { ItemComponent } from './item/item.component';
import { DrinksService } from './drinks.service';
import { interval, Observable } from 'rxjs';
import { WebcamImage, WebcamModule } from 'ngx-webcam';
import {webSocket} from "rxjs/webSocket";

interface DetectApp{
  n_images:Number;
  saved_images:Number;
  app_mode: Number;
  user_id: Number;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, ItemComponent, WebcamModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})

export class AppComponent {
  title = 'Beer Ranking';
  componentTitle = "Beer Ranking";
  captureImageData:boolean = true
  refreshSubscription;
  observableSnapshot;
  wsSocketProtocol = location.protocol === 'http:' ? 'ws' : 'wss';
  editing = false;
  recognizedFaces:Array<Array<number>> = [];
  webCamArea:HTMLCanvasElement | null = null;

  wsSubject = webSocket(
    {
      url: this.wsSocketProtocol + '://' + location.hostname + ':8000/face-detection',
      binaryType: 'blob',
      serializer: v => v as Uint8ClampedArray,
    }
  );

  facingMode: string = 'user';  //Set front camera
  allowCameraSwitch = false;
  
  
  public get videoOptions(): MediaTrackConstraints {
      const result: MediaTrackConstraints = {};
      if (this.facingMode && this.facingMode !== '') {
          result.facingMode = { ideal: this.facingMode };
      }
      return result;
  }

  refreshDrinkers(){
    var tempDrinkers:Drinker[] = [];
    this.drinksService.getDrinkers().subscribe(item => {
      item.forEach(drinker => {
        var temp = drinker;
        //console.log(temp);
        temp.quantity = temp.drinks!.reduce((accumulator,val) => accumulator+val.quantity,0)
        tempDrinkers.push(temp)
      });
      tempDrinkers.sort((a,b) => b.quantity - a.quantity);
      this.allDrinkers = tempDrinkers;
    });
  }

  constructor(private drinksService: DrinksService){
    this.refreshDrinkers();
    this.refreshSubscription = interval(5000).subscribe(
      val => {
        console.log(val); 
        this.refreshDrinkers();
      }
    );

    //Take snapshots of the webcam
    this.observableSnapshot = new Observable<void>(
      observer => {
        setInterval(()=>{
                  observer.next(void 0);
                  //console.log("Observer called");
                },500)
              }
        );

    //Subscribe to the web socket
    this.wsSubject.subscribe({
      next: (msg) => { 
        if(typeof msg === "object" && msg && "faces" in msg)
          this.recognizedFaces = msg['faces'] as Array<Array<number>>;
        if(!this.webCamArea){
          this.webCamArea = document.getElementById("face-canvas") as HTMLCanvasElement;
          this.webCamArea.height = this.webCamArea.clientHeight;
          this.webCamArea.width = this.webCamArea.clientWidth;
        }
        else{
          let ctx = this.webCamArea.getContext('2d');
          if (ctx){
            ctx.beginPath();
            ctx.clearRect(0,0,this.webCamArea.width,this.webCamArea.height)

            if(typeof msg === "object" && msg && "app_state" in msg && "detected_face" in msg){
              let curr_mode = msg['app_state'] as DetectApp;
              console.log(msg['detected_face']);
              if(curr_mode.app_mode == 1)
              {
                console.log("recording images")
                let quarterX = this.webCamArea.width*1.0/4;
                let quarterY = this.webCamArea.height*1.0/6;
                ctx.fillStyle = 'rgba(200, 0, 0, 0.5)'; // Example: semi-transparent red
                ctx.fillRect(0, 0, this.webCamArea.width, quarterY); 
                ctx.fillRect(0, quarterY, quarterX, 4*quarterY);
                ctx.fillRect(3*quarterX, quarterY, quarterX, 4*quarterY);
                ctx.fillRect(0, 5*quarterY, this.webCamArea.width, quarterY);
              }
              else
              {
                console.log("detecting")
              }
              for (const [x,y,width,height] of this.recognizedFaces){
                ctx.strokeStyle = "#49fb35";
                ctx.beginPath();
                ctx.rect(x,y,width,height);
                ctx.stroke();
              }
            }
          }
        }
      },
      error: (err) => console.log(err),
      complete: () => console.log("Connection closed")
      }
    )
  }

  filter: "all" | "active" | "active" = "all";

  allDrinkers2 = []

  allDrinkers = [
    { 
      id:0,
      name: "Placeholder",
      nickname: "Place",
      quantity: 0,
      active: false,
      email: '',
    },
  ];

  

  addDrinker(name:string, email:string, nickname:string){
    if(!name) return;
    this.drinksService.addDrinker(
      {
        id:0,
        name:name,
        email:email,
        nickname:nickname,
        active: false,
        quantity:0,
      }
    );

    this.refreshDrinkers();
  }

  remove(item: Drinker){
    this.allDrinkers.splice(this.allDrinkers.indexOf(item),1);
  }

  editableToggle(flag: boolean){
    console.log("toogle!")
    if(flag)
    {
      this.refreshSubscription.unsubscribe()
    }
    else
    {
      this.refreshSubscription = interval(5000).subscribe(
        val => {
          console.log(val); 
          this.refreshDrinkers();
        }
      );
    }
  }

  totalQuantity(): string{
    var total = this.drinkers.reduce((accumulator,val) => accumulator+val.quantity,0);
    return formatNumber(total/1000,"en-US","1.1-1");
  }

  getActiveUser(): string{
    var drinker = this.drinkers.filter(x => x.active == true);
    if(drinker.length > 0)
      return drinker[0].name;
    else
      return "";
  }

  get drinkers() {
    if (this.filter === "all") {
      return this.allDrinkers;
    }

    return this.allDrinkers.filter((item) => 
      this.filter==="active" ? item.active : !item.active
    );
  }

  private lastFrameData: Uint8ClampedArray | null = null;
  private lastSentTime: number = 0;
  private motionThreshold: number = 30; // Threshold for pixel difference
  private minMotionPixels: number = 500; // Minimum number of changed pixels to trigger motion

  processCamSnapshot(camImage: WebcamImage){
    const now = Date.now();
    if (now - this.lastSentTime < 500) {
      return; // Rate limit to 500ms
    }

    if (this.detectMotion(camImage)) {
      this.wsSubject.next(camImage.imageAsDataUrl);
      this.lastSentTime = now;
    }
  }

  private motionCanvas: HTMLCanvasElement = document.createElement('canvas');

  private detectMotion(camImage: WebcamImage): boolean {
    if (!this.lastFrameData) {
      this.updateLastFrame(camImage);
      return true;
    }

    const currentFrameData = this.getFrameData(camImage);
    if (!currentFrameData) return true;

    let diffCount = 0;
    for (let i = 0; i < currentFrameData.length; i += 4) {
      // Simple difference calculation (averaging R, G, B channels)
      const rDiff = Math.abs(currentFrameData[i] - this.lastFrameData[i]);
      const gDiff = Math.abs(currentFrameData[i+1] - this.lastFrameData[i+1]);
      const bDiff = Math.abs(currentFrameData[i+2] - this.lastFrameData[i+2]);
      
      if ((rDiff + gDiff + bDiff) / 3 > this.motionThreshold) {
        diffCount++;
      }
    }

    this.lastFrameData = currentFrameData;
    return diffCount > this.minMotionPixels;
  }

  private updateLastFrame(camImage: WebcamImage) {
    this.lastFrameData = this.getFrameData(camImage);
  }

  private getFrameData(camImage: WebcamImage): Uint8ClampedArray | null {
    const ctx = this.motionCanvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return null;
    
    // Resize canvas if needed
    const width = camImage.imageData.width;
    const height = camImage.imageData.height;
    if (this.motionCanvas.width !== width || this.motionCanvas.height !== height) {
      this.motionCanvas.width = width;
      this.motionCanvas.height = height;
    }
    
    // We can use the imageData directly from camImage if it's available
    return camImage.imageData.data;
  }


  //Start of code for processing camera feed


}

