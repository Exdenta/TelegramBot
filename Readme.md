

## 1. Основной функционал

Знакомство с API ВКонтакте https://vk.com/dev/first_guide

```
pip install virtualenv
python -m venv env
env\Scripts\activate
pip install -r requirement.txt
```

## 2. Опционально. Генерирование текста

### 2.1 Установка CUDA и cuDNN (при наличии ввидеокарты NVIDIA)

Установить CUDA v10.1 - https://developer.nvidia.com/cuda-10.1-download-archive-base
Скачать и установить cuDNN v7.6 для CUDA v10.1 - https://developer.nvidia.com/rdp/cudnn-archive

```
pip install -r requirements_gpt.txt
pip install torch==1.5.1+cu101 torchvision==0.6.1+cu101 -f https://download.pytorch.org/whl/torch_stable.html
```