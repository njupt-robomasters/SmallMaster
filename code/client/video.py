import av
import cv2

import threading
from collections import deque
import time
import logging

# ffmpeg列出摄像头
# ffmpeg -list_devices true -f dshow -i dummy

class Video(threading.Thread):
    def __init__(self, level=logging.WARNING):
        super().__init__(daemon=True)

        self.logger = logging.getLogger("Video")
        self.logger.setLevel(level)

        # 可读取
        self.frame = None
        self.fps = None

        self._source = None
        self._container = None
        self._timestamps = deque()  # 用于统计视频帧率

    def set_source(self, source):
        if source == self._source:
            return

        self.logger.info(f"视频源变更: {self._source} -> {source}")
        self._source = source

        self._reset()

    def run(self):
        self.logger.info("视频线程启动")

        while True:
            if self._source is None:
                time.sleep(0.1)
                continue

            if self._container is None:
                self.logger.info(f"尝试连接视频源: {self._source}")
                try:
                    if self._source.startswith("video="):
                        self._container = av.open(self._source, format='dshow') 
                    elif self._source.startswith("/dev"):
                        self._container = av.open(self._source, format='v4l2') 
                    else:
                        self._container = av.open(self._source, options={"timeout": "3000000"})  # 超时3秒（单位：微秒）
                    self.logger.info(f"视频源连接成功")
                except Exception as e:
                    self.logger.info(f"连接视频源报错: {e}")
                    time.sleep(0.1)
                    continue

            self._read()

    def _read(self):
        try:
            av_frame = next(self._container.decode(video=0))
            # PyAV 返回的帧是 AVFrame 对象，需要转换为 numpy 数组给 OpenCV 使用（BGR格式）
            frame = av_frame.to_ndarray(format="bgr24")
            height, width = frame.shape[:2]
            if height > width:
                self.frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            else:
                self.frame = frame
            self._update_fps()
        except Exception as e:
            if e.errno == 1094995529:
                return
            self.logger.error(f"读取视频流报错: {e}")
            self._reset()
            return

    def _update_fps(self):
        """更新帧时间戳"""
        self._timestamps.append(time.time())

        # 清理超过1秒的时间戳
        while self._timestamps and time.time() - self._timestamps[0] > 1.0:
            self._timestamps.popleft()

        self.fps = len(self._timestamps)
        self.logger.debug(f"视频流帧率 {self.fps} FPS")

    def _reset(self):
        if self._container:
            self._container.close()
            self._container = None

        self.frame = None
        self.fps = None
        self._timestamps.clear()


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    video = Video(logging.INFO)
    video.start()
    # source = "rtsp://192.168.1.1:7070/webcam"
    # source = "video=Integrated Camera"
    source = "video=USB Video"
    video.set_source(source)

    while True:
        if video.frame is not None:
            cv2.imshow(source, video.frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cv2.destroyAllWindows()
