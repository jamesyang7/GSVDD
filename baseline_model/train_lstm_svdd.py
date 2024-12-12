
import os
import sys
sys.path.append("../")
import torch.nn as nn
import numpy as np
from random import shuffle
import torch
import torch.optim as optim
import torch.optim.lr_scheduler as lr_scheduler
from torch.utils.data import DataLoader
from tqdm import tqdm
from dataloader.svdd_dataloader import CollisionLoader_new 
from baseline_lstm_svdd_net import FusionNet
from reconstruction_loss import ReconstructionLoss

torch.manual_seed(42)
np.random.seed(42)

train_audio_path = '../../data/audio/normal_train'
train_imu_path = '../../data/imu/normal_train'

test_audio_path = '../../data/audio/abnormal'
test_imu_path = '../../data/imu/abnormal'

checkpoint_path = ''
save_path = '/home/iot/collision_detect/output/baselinemodel'
workers = 4
batchsize = 256
dropout_rate = 0.3
kernel_num = 32
feature_dim = 512
num_class = 2
use_attention = 0
Epoch = 200
hidden_dim = 64  # LSTM隐藏层维度
num_layers = 2  # LSTM层数
save_name = "svdd_{}_".format(use_attention)
save_dir = os.path.join(save_path, save_name)
os.makedirs(save_dir, exist_ok=True)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(device)

train_data = CollisionLoader_new(train_imu_path,train_audio_path)
val_data   = CollisionLoader_new(test_imu_path,test_audio_path)
train_dataloader = DataLoader(train_data, batchsize, shuffle=True, num_workers=workers, drop_last=True)
val_dataloader   = DataLoader(val_data, batchsize, shuffle=True, num_workers=workers, drop_last=True)


# model = FusionNet(use_crossattention=use_attention, feature_dim=feature_dim, dropout_rate=dropout_rate, kernel_num=kernel_num, classes=num_class)
model = FusionNet(feature_dim=feature_dim, threshold=0.5, lstm_input_dim=20, lstm_hidden_dim=hidden_dim, lstm_num_layers=num_layers)
model = model.to(device)

if checkpoint_path != '':
    model.load_state_dict(torch.load(checkpoint_path))

optimizer  = optim.Adam(model.parameters(), lr=0.0001, betas=(0.9, 0.999))
scheduler  = optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.8)


reconstruction_loss_fn = ReconstructionLoss()
loss_function = nn.MSELoss()
random_tensor = torch.randn(feature_dim * 2).to(device)
best_val_loss = float('inf')
best_model_state_dict = None

torch.save(random_tensor, 'center.pth')
for epoch in range(Epoch):
    model.train()
    total_train_loss = 0
    total_svdd_loss = 0
    total_reconstruction_loss = 0

    for i, data in enumerate(train_dataloader, 0):
        spec, image, audio = data
        spec, image, audio = spec.to(device), image.to(device), audio.to(device)
        target_zero = random_tensor.unsqueeze(0).expand(batchsize, -1)


        optimizer.zero_grad()
        anomaly_score= model(audio, image)
        target_zero = random_tensor.unsqueeze(0).expand(batchsize, -1)

        svdd_loss = loss_function(anomaly_score, target_zero)
        total_svdd_loss += svdd_loss.item()

        total_loss = svdd_loss
        total_loss.backward()
        optimizer.step()

        total_train_loss += total_loss.item()

    mean_train_loss = total_train_loss / len(train_dataloader)
    # mean_svdd_loss = total_svdd_loss / len(train_dataloader)
    # mean_reconstruction_loss = total_reconstruction_loss / len(train_dataloader)

    print(f"Epoch [{epoch+1}/{Epoch}], Train Loss: {mean_train_loss:.4f}")

    if (epoch + 1) % 1 == 0:
        model.eval()
        total_val_loss = 0
        total_val_svdd_loss = 0
        total_val_reconstruction_loss = 0

        with torch.no_grad():
            for i, data in enumerate(val_dataloader, 0):
                spec, image, audio = data
                spec, image, audio = spec.to(device), image.to(device), audio.to(device)

                anomaly_score = model(audio, image)

                target_zero = random_tensor.unsqueeze(0).expand(batchsize, -1)
                svdd_loss = loss_function(anomaly_score, target_zero)
                total_val_svdd_loss += svdd_loss.item()

                # reconstruction_loss = reconstruction_loss_fn(image, reconstructed_imu, audio, reconstructed_audio)
                # total_val_reconstruction_loss += reconstruction_loss.item()

                total_loss = svdd_loss
                total_val_loss += total_loss.item()

        mean_val_loss = total_val_loss / len(val_dataloader)
        # mean_val_svdd_loss = total_val_svdd_loss / len(val_dataloader)
        # mean_val_reconstruction_loss = total_val_reconstruction_loss / len(val_dataloader)

        print(f"Epoch [{epoch+1}/{Epoch}], Validation Loss: {mean_val_loss:.4f}")


# torch.save(model.state_dict(), 'lstm_svdd_last_model.pth')
        torch.save(model.state_dict(), os.path.join(save_dir, 'lstm_svdd_last_model.pth'))
        # print(f"Model will be saved to: {os.path.join(save_dir, 'lstm_svdd_last_model.pth')}")


